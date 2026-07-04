// Package agent implements the checkout agent.
// It receives a PlaceOrder request, constructs a system+user prompt describing
// the checkout task, then runs a ReAct loop:
//
//  1. Send messages + tool definitions to Ollama.
//  2. If the model emits tool_calls, dispatch them to the real gRPC services.
//  3. Feed results back as tool messages.
//  4. Repeat until the model emits a final text message containing the order
//     summary JSON (or returns an error).
package agent

import (
	pb "checkoutservice-agent/genproto"
	"checkoutservice-agent/ollama"
	"checkoutservice-agent/tools"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/google/uuid"
	"github.com/sirupsen/logrus"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const maxIterations = 20

func getFaultMode() string {
	return os.Getenv("FAULT_MODE")
}

func getBusinessException() string {
	return os.Getenv("BUSINESS_EXCEPTION")
}

func isInventoryMismatchEnabled() bool {
	return getBusinessException() == "inventory_mismatch"
}

// Fault injection logic for inventory mismatch scenario

func applyCheckoutFaults(toolName string, result string, log *logrus.Logger) string {
	faultMode := getFaultMode()

	if !isInventoryMismatchEnabled() {
		return result
	}

	// FM-2.4: Information Withholding
	// Product/inventory mismatch exists, but checkout receives only "stock available".
	if faultMode == "FM-2.4" && toolName == "get_product" {
		log.Warn("[FAULT_INJECTION] FM-2.4 active: hiding inventory mismatch from checkout")
		return `{
			"status": "stock_available",
			"catalog_stock": 5,
			"actual_stock": 0,
			"mismatch_hidden": true,
			"message_to_checkout": "stock_available"
		}`
	}

	// Inventory mismatch visible to checkout.
	if toolName == "get_product" {
		log.Warn("[FAULT_INJECTION] inventory_mismatch active: returning mismatch result")
		return `{
			"status": "inventory_mismatch_detected",
			"catalog_stock": 5,
			"actual_stock": 0,
			"mismatch": true,
			"message_to_checkout": "STOP_CHECKOUT"
		}`
	}

	return result
}

// Config holds all addresses the agent needs.
type Config struct {
	CartSvcAddr        string
	ProductCatalogAddr string
	CurrencySvcAddr    string
	ShippingSvcAddr    string
	PaymentSvcAddr     string
	EmailSvcAddr       string
	OllamaAddr         string
	OllamaModel        string
}

// CheckoutAgent orchestrates the checkout flow via an LLM tool-use loop.
type CheckoutAgent struct {
	cfg   Config
	llm   *ollama.Client
	tools map[string]tools.Tool
	defs  []ollama.ToolDefinition
	log   *logrus.Logger
}

// New creates a CheckoutAgent, wiring up all downstream gRPC tool clients.
func New(cfg Config, log *logrus.Logger) (*CheckoutAgent, error) {
	a := &CheckoutAgent{
		cfg:   cfg,
		llm:   ollama.New(cfg.OllamaAddr, cfg.OllamaModel),
		tools: make(map[string]tools.Tool),
		log:   log,
	}

	register := func(t tools.Tool, err error) error {
		if err != nil {
			return err
		}
		a.tools[t.Name()] = t
		a.defs = append(a.defs, t.Definition())
		return nil
	}

	// Register all tools (one per downstream gRPC service / operation).
	if err := register(tools.NewGetCartTool(cfg.CartSvcAddr)); err != nil {
		return nil, fmt.Errorf("get_cart tool: %w", err)
	}
	if err := register(tools.NewEmptyCartTool(cfg.CartSvcAddr)); err != nil {
		return nil, fmt.Errorf("empty_cart tool: %w", err)
	}
	if err := register(tools.NewGetProductTool(cfg.ProductCatalogAddr)); err != nil {
		return nil, fmt.Errorf("get_product tool: %w", err)
	}
	if err := register(tools.NewConvertCurrencyTool(cfg.CurrencySvcAddr)); err != nil {
		return nil, fmt.Errorf("convert_currency tool: %w", err)
	}
	if err := register(tools.NewQuoteShippingTool(cfg.ShippingSvcAddr)); err != nil {
		return nil, fmt.Errorf("quote_shipping tool: %w", err)
	}
	if err := register(tools.NewShipOrderTool(cfg.ShippingSvcAddr)); err != nil {
		return nil, fmt.Errorf("ship_order tool: %w", err)
	}
	if err := register(tools.NewChargeCardTool(cfg.PaymentSvcAddr)); err != nil {
		return nil, fmt.Errorf("charge_card tool: %w", err)
	}
	if err := register(tools.NewSendConfirmationTool(cfg.EmailSvcAddr)); err != nil {
		return nil, fmt.Errorf("send_order_confirmation tool: %w", err)
	}

	return a, nil
}

// Close is a no-op placeholder; gRPC connections are closed per-request
// (stateless dial in tools). Extend here if you want pooled connections.
func (a *CheckoutAgent) Close() {}

// PlaceOrder is the entry point called by the gRPC server.
// It builds the initial prompt and runs the ReAct loop.
func (a *CheckoutAgent) PlaceOrder(ctx context.Context, req *pb.PlaceOrderRequest) (*pb.PlaceOrderResponse, error) {
	orderID := uuid.New().String()
	a.log.Infof("[agent] starting order=%s user=%s currency=%s", orderID, req.UserId, req.UserCurrency)

	systemPrompt := `You are a checkout agent for an e-commerce platform.

You MUST follow the tool-calling process internally, but you MUST NOT output tool calls.

You MUST NOT output:
- tool names
- intermediate steps
- reasoning
- multiple objects

You MUST ONLY output ONE valid JSON object.

STRICT RULES:
- Output MUST start with '{' and end with '}'
- No text before or after
- No markdown
- No explanations
- No tool traces
- No multiple JSON objects

FINAL OUTPUT FORMAT:
{
  "order_id": "<orderID>",
  "shipping_tracking_id": "<trackingID>",
  "shipping_cost": {"currency_code":"...","units":0,"nanos":0},
  "shipping_address": {
    "street_address":"...",
    "city":"...",
    "state":"...",
    "country":"...",
    "zip_code": 0
  },
  "items": [
    {
      "item":{"product_id":"...","quantity":0},
      "cost":{"currency_code":"...","units":0,"nanos":0}
    }
  ]
}

CRITICAL INVALID OUTPUTS:
You must NEVER output JSON containing:
- "type": "function"
- "function"
- "parameters"
- "name": "quote_shipping"
- "name": "ship_order"
- "name": "get_product"

Those are internal tool calls, not final answers.

If you need to call a tool, call it internally using the tool-calling interface.
The final message must only be the final checkout result JSON.

If you output anything else, the system will fail.`

	userMsg := fmt.Sprintf(`Process checkout for:
- order_id: %s
- user_id: %s
- user_currency: %s
- email: %s
- address_street: %s
- address_city: %s
- address_state: %s
- address_country: %s
- address_zip: %d
- credit_card: number=%s expiry=%d/%d cvv=%s`,
		orderID,
		req.UserId,
		req.UserCurrency,
		req.Email,
		req.Address.StreetAddress,
		req.Address.City,
		req.Address.State,
		req.Address.Country,
		req.Address.ZipCode,
		req.CreditCard.CreditCardNumber,
		req.CreditCard.CreditCardExpirationMonth,
		req.CreditCard.CreditCardExpirationYear,
		req.CreditCard.CreditCardCvv,
	)
	messages := []ollama.Message{
		{Role: "system", Content: systemPrompt},
		{Role: "user", Content: userMsg},
	}

	// ReAct loop
	for i := 0; i < maxIterations; i++ {
		a.log.Debugf("[agent] iteration %d  calling LLM", i+1)

		reply, err := a.llm.Chat(ctx, messages, a.defs)
		if err != nil {
			return nil, status.Errorf(codes.Internal, "LLM error: %v", err)
		}

		// Append assistant message to history
		messages = append(messages, *reply)

		// incomplete verification fault 3.2 missing final checks

		if len(reply.ToolCalls) == 0 {
			a.log.Infof("[agent] final answer received for order=%s", orderID)

			if isInventoryMismatchEnabled() && getFaultMode() != "FM-3.2" {
				if strings.Contains(reply.Content, `"shipping_tracking_id"`) {
					a.log.Warn("[FAULT_INJECTION] Final verification detected inventory mismatch. Blocking checkout.")
					return nil, status.Errorf(codes.FailedPrecondition, "inventory mismatch detected during final verification")
				}
			}

			if isInventoryMismatchEnabled() && getFaultMode() == "FM-3.2" {
				a.log.Warn("[FAULT_INJECTION] FM-3.2 active: final inventory verification skipped")
			}

			return parseOrderResponse(reply.Content, req)
		}

		// Dispatch every tool call and collect results
		for _, tc := range reply.ToolCalls {
			toolName := tc.Function.Name
			a.log.Infof("[agent] tool_call id=%s name=%s args=%s", tc.ID, toolName, tc.Function.Arguments)

			tool, ok := a.tools[toolName]
			if !ok {
				errMsg := fmt.Sprintf("unknown tool: %s", toolName)
				a.log.Warnf("[agent] %s", errMsg)
				messages = append(messages, ollama.Message{
					Role:       "tool",
					ToolCallID: tc.ID,
					Content:    fmt.Sprintf(`{"error":"%s"}`, errMsg),
				})
				continue
			}

			args, err := parseArguments(tc.Function.Arguments)
			if err != nil {
				return nil, fmt.Errorf("parse arguments: %w", err)
			}
			result, err := tool.Execute(ctx, args)

			if err != nil {
				a.log.Warnf("[agent] tool %s error: %v", toolName, err)
				result = fmt.Sprintf(`{"error":"%v"}`, err)
			}

			// Apply inventory mismatch and FM-2.4 fault injection
			result = applyCheckoutFaults(toolName, result, a.log)

			// FM-1.3: Step Repetition
			// Send the same tool result twice to the LLM
			if isInventoryMismatchEnabled() &&
				getFaultMode() == "FM-1.3" &&
				toolName == "get_product" {

				a.log.Warn("[FAULT_INJECTION] FM-1.3 active: repeating get_product result")

				messages = append(messages, ollama.Message{
					Role:       "tool",
					ToolCallID: tc.ID,
					Content:    result,
				})
			}

			a.log.Debugf("[agent] tool %s result: %s", toolName, result)

			messages = append(messages, ollama.Message{
				Role:       "tool",
				ToolCallID: tc.ID,
				Content:    result,
			})
		}
	}

	return nil, status.Errorf(codes.Internal, "agent exceeded max iterations (%d) without completing checkout", maxIterations)
}

// parseOrderResponse parses the model's final JSON text into a PlaceOrderResponse.
func parseOrderResponse(content string, req *pb.PlaceOrderRequest) (*pb.PlaceOrderResponse, error) {
	var result struct {
		OrderID            string `json:"order_id"`
		ShippingTrackingID string `json:"shipping_tracking_id"`
		ShippingCost       struct {
			CurrencyCode string `json:"currency_code"`
			Units        int64  `json:"units"`
			Nanos        int32  `json:"nanos"`
		} `json:"shipping_cost"`
		Items []struct {
			Item struct {
				ProductID string `json:"product_id"`
				Quantity  int32  `json:"quantity"`
			} `json:"item"`
			Cost struct {
				CurrencyCode string `json:"currency_code"`
				Units        int64  `json:"units"`
				Nanos        int32  `json:"nanos"`
			} `json:"cost"`
		} `json:"items"`
	}

	cleaned := extractFirstJSON(content)

	if strings.Contains(cleaned, `"type":"function"`) ||
		strings.Contains(cleaned, `"function"`) ||
		strings.Contains(cleaned, `"parameters"`) ||
		strings.Contains(cleaned, `"quote_shipping"`) ||
		strings.Contains(cleaned, `"ship_order"`) ||
		strings.Contains(cleaned, `"get_product"`) {
		return nil, status.Errorf(
			codes.Internal,
			"LLM returned tool-call/schema JSON instead of final order JSON: %s",
			cleaned,
		)
	}
	if err := json.Unmarshal([]byte(cleaned), &result); err != nil {
		return nil, status.Errorf(codes.Internal, "failed to parse agent final answer: %v — raw: %s", err, content)
	}

	var orderItems []*pb.OrderItem
	for _, oi := range result.Items {
		orderItems = append(orderItems, &pb.OrderItem{
			Item: &pb.CartItem{ProductId: oi.Item.ProductID, Quantity: oi.Item.Quantity},
			Cost: &pb.Money{CurrencyCode: oi.Cost.CurrencyCode, Units: oi.Cost.Units, Nanos: oi.Cost.Nanos},
		})
	}

	return &pb.PlaceOrderResponse{
		Order: &pb.OrderResult{
			OrderId:            result.OrderID,
			ShippingTrackingId: result.ShippingTrackingID,
			ShippingCost: &pb.Money{
				CurrencyCode: result.ShippingCost.CurrencyCode,
				Units:        result.ShippingCost.Units,
				Nanos:        result.ShippingCost.Nanos,
			},
			ShippingAddress: req.Address,
			Items:           orderItems,
		},
	}, nil
}
func parseArguments(args json.RawMessage) (string, error) {
	var s string
	if err := json.Unmarshal(args, &s); err == nil {
		return s, nil
	}
	return string(args), nil
}
func extractFirstJSON(content string) string {
	depth := 0
	start := strings.Index(content, "{")
	if start == -1 {
		return content
	}
	inString := false
	escaped := false
	for i := start; i < len(content); i++ {
		c := content[i]
		if escaped {
			escaped = false
			continue
		}
		if c == '\\' && inString {
			escaped = true
			continue
		}
		if c == '"' {
			inString = !inString
			continue
		}
		if inString {
			continue
		}
		if c == '{' {
			depth++
		} else if c == '}' {
			depth--
			if depth == 0 {
				return strings.TrimSpace(content[start : i+1])
			}
		}
	}
	return content
}

// normalizeJSON attempts to fix common LLM JSON mistakes:
// - numbers sent as strings ? convert to numbers
// - arrays sent as stringified JSON ? decode them
func normalizeJSON(input string) (string, error) {
	var raw map[string]any
	if err := json.Unmarshal([]byte(input), &raw); err != nil {
		return "", err
	}

	for k, v := range raw {
		switch val := v.(type) {

		// Fix numbers passed as strings
		case string:
			// Try int
			var i int64
			if _, err := fmt.Sscanf(val, "%d", &i); err == nil {
				raw[k] = i
				continue
			}

			// Try float (optional)
			var f float64
			if _, err := fmt.Sscanf(val, "%f", &f); err == nil {
				raw[k] = f
				continue
			}

			// Try JSON array/object inside string
			var parsed any
			if err := json.Unmarshal([]byte(val), &parsed); err == nil {
				raw[k] = parsed
				continue
			}
		}
	}

	out, err := json.Marshal(raw)
	if err != nil {
		return "", err
	}
	return string(out), nil
}
