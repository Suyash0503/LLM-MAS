"""
ShippingOrchestrator (Llama 3 variant)
=======================================
Replaces the Anthropic SDK with calls to a self-hosted Llama 3 instance
running as an OpenAI-compatible endpoint inside the Kubernetes cluster
(e.g. via vLLM, Ollama, or llama.cpp server).

Key difference from the Claude version:
  Llama 3 does not natively support tool-use in the same structured way.
  This orchestrator implements a **ReAct loop** (Reason → Act → Observe)
  using a strict prompt format that Llama 3 Instruct can reliably follow.

ReAct format used:
  Thought: <reasoning>
  Action: <tool_name>
  Action Input: <json args>
  ---
  Observation: <tool result injected by orchestrator>
  ... (repeat until)
  Final Answer: <json result>

Environment variables:
  LLAMA_BASE_URL   — OpenAI-compatible base URL, e.g. http://llama-service:8000/v1
  LLAMA_MODEL      — model name to pass in the request, e.g. "meta-llama/Meta-Llama-3-8B-Instruct"
  PORT             — gRPC port (default 50051)
"""

import json
import logging
import os
import re
import requests

from agents.quote_agent import QuoteAgent
from agents.carrier_agent import CarrierSelectionAgent
from agents.tracking_agent import TrackingAgent

log = logging.getLogger(__name__)

LLAMA_BASE_URL = os.environ.get("LLAMA_BASE_URL", "http://ollama:/v1")
LLAMA_MODEL    = os.environ.get("LLAMA_MODEL", "llama3:latest")

MAX_ITERATIONS = 8   # safety cap on ReAct loop turns
MAX_TOKENS     = 512


# ── Tool registry (same logical tools as Claude version) ─────────────────────

TOOL_DESCRIPTIONS = """You have access to these tools:

1. get_shipping_quote
   Description: Estimates the USD shipping cost for a destination address and cart items.
   Input JSON schema:
     { "address": {"city": str, "country": str, "state": str, "zip_code": int},
       "items": [{"product_id": str, "quantity": int}] }
   Returns: {"cost_usd": float, "breakdown": {...}}

2. select_carrier
   Description: Selects the best shipping carrier given the destination, cost, and item count.
   Input JSON schema:
     { "address": {"country": str, "state": str, "zip_code": int},
       "cost_usd": float,
       "item_count": int }
   Returns: {"carrier": str, "service_level": str, "estimated_delivery_days": int, "reason": str}

3. generate_tracking_id
   Description: Generates a unique carrier-formatted tracking ID and registers the shipment.
   Input JSON schema:
     { "carrier": str, "address": {"city": str, "country": str}, "item_count": int }
   Returns: {"tracking_id": str, "carrier": str, "registered": bool}

Use the following format EXACTLY — no deviations:

Thought: <your reasoning about what to do next>
Action: <tool name, one of: get_shipping_quote | select_carrier | generate_tracking_id>
Action Input: <valid JSON matching the tool's input schema>

When you have the final answer, output:
Final Answer: <valid JSON with the result>
"""


REACT_SYSTEM_PROMPT = (
    "You are a shipping logistics agent. "
    "Solve tasks step-by-step. "
    "Always use Thought/Action/Action Input/Final Answer format exactly. "
    "Keep Thought sections under 2 sentences. Do not explain tool schemas."  # ? add this
)


class ShippingOrchestrator:
    """
    Orchestrates shipping operations using Llama 3 (self-hosted) as the
    reasoning engine, via a ReAct prompting loop.
    Sub-agents are identical to the Claude version — fully reusable.
    """

    def __init__(self):
        self.base_url = LLAMA_BASE_URL.rstrip("/")
        self.model    = LLAMA_MODEL
        self.quote_agent   = QuoteAgent()
        self.carrier_agent = CarrierSelectionAgent()
        self.tracking_agent = TrackingAgent()
        log.info(f"ShippingOrchestrator (Llama) ready — endpoint={self.base_url}, model={self.model}")

    # ── Llama inference call ──────────────────────────────────────────────────

    def _call_llama(self, messages: list, stop: list = None) -> str:
        """
        Call the Llama 3 OpenAI-compatible chat completions endpoint.
        Returns the assistant message text.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": MAX_TOKENS,
            "temperature": 0.0,   # deterministic for agentic use
        }
        if stop:
            payload["stop"] = stop

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=(60,120),
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"].strip()

            usage = data.get("usage", {})

            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

            print(f"TOKEN_METRICS input={input_tokens} output={output_tokens} total={total_tokens}")

            with open("token_log.txt", "a") as f:
             f.write(f"{total_tokens}\n")

            return content
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(
                f"Cannot reach Llama endpoint at {self.base_url}. "
                f"Ensure the llama-service pod is running. Error: {e}"
            )
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Llama API HTTP error: {e} — {resp.text[:200]}")

    # ── ReAct parser ──────────────────────────────────────────────────────────

    def _parse_react_output(self, text: str):
        """
        Parse a single ReAct turn from Llama's output.
        Returns one of:
          ("action",   tool_name, tool_input_dict)
          ("final",    result_str,  None)
          ("unknown",  raw_text,    None)
        """
        # Final Answer
        fa_match = re.search(r"Final Answer:\s*(\{.*\})", text, re.DOTALL)
        if fa_match:
            return ("final", fa_match.group(1).strip(), None)

        # Action block — bracket-depth counter handles nested JSON correctly
        action_match = re.search(r"Action:\s*(\w+)", text)
        ai_start = re.search(r"Action Input:\s*(\{)", text)

        if action_match and ai_start:
            tool_name = action_match.group(1).strip()
            # Walk forward to find the matching closing brace
            start = ai_start.start(1)
            depth, end = 0, start
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            raw_json = text[start:end]
            try:
                tool_input = json.loads(raw_json)
            except json.JSONDecodeError as e:
                log.warning(f"Failed to parse Action Input JSON: {e}\nRaw: {raw_json}")
                tool_input = {}
            return ("action", tool_name, tool_input)

        return ("unknown", text, None)

    # ── Tool dispatcher (identical interface to Claude version) ───────────────

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> str:
        log.debug(f"Dispatching tool: {tool_name}, input={tool_input}")

        if tool_name == "get_shipping_quote":
            result = self.quote_agent.estimate(
                tool_input.get("address", {}), tool_input.get("items", [])
            )
        elif tool_name == "select_carrier":
            result = self.carrier_agent.select(
                tool_input.get("address", {}),
                float(tool_input.get("cost_usd", 0)),
                int(tool_input.get("item_count", 1)),
            )
        elif tool_name == "generate_tracking_id":
            result = self.tracking_agent.generate(
                tool_input.get("carrier", "FedEx"),
                tool_input.get("address", {}),
                int(tool_input.get("item_count", 1)),
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        log.debug(f"Tool result: {result}")
        return json.dumps(result)

    # ── ReAct agentic loop ────────────────────────────────────────────────────

    def _run_agent_loop(self, task_prompt: str) -> str:
        """
        Runs the ReAct loop:
          1. Send system + task to Llama, stopping at "Observation:"
          2. Parse Action or Final Answer
          3. If Action → dispatch tool, append Observation, continue
          4. If Final Answer → return it
          5. Cap at MAX_ITERATIONS to prevent runaway loops
        """
        # Build the initial conversation
        messages = [
            {"role": "system", "content": REACT_SYSTEM_PROMPT},
            {"role": "user",   "content": TOOL_DESCRIPTIONS + "\n\n" + task_prompt},
        ]
        #messages = [
        #    {"role": "system", "content": REACT_SYSTEM_PROMPT},
        #    {"role": "user",   "content": task_prompt},
        #]

        # Running scratchpad — we append Observations inline into the
        # assistant message to simulate a single growing context
        scratchpad = ""

        for iteration in range(MAX_ITERATIONS):
            log.debug(f"ReAct iteration {iteration + 1}/{MAX_ITERATIONS}")

            # Ask Llama to continue from current scratchpad
            current_messages = messages.copy()
            if scratchpad:
                # Append the accumulated reasoning as a partial assistant turn
                current_messages.append(
                    {"role": "assistant", "content": scratchpad}
                )
                # Ask Llama to continue
                current_messages.append(
                    {"role": "user", "content": "Continue."}
                )

            llama_output = self._call_llama(
                current_messages,
                stop=["Observation:"],  # stop before writing its own observation
            )

            log.debug(f"Llama output:\n{llama_output}")
            scratchpad += "\n" + llama_output

            kind, value, tool_input = self._parse_react_output(llama_output)

            if kind == "final":
                log.info(f"Agent reached Final Answer after {iteration + 1} iterations")
                return value

            elif kind == "action":
                tool_result = self._dispatch_tool(value, tool_input)
                observation = f"\nObservation: {tool_result}\n"
                scratchpad += observation
                log.debug(f"Appended observation: {observation.strip()}")

            else:
                # Llama produced unexpected output — log and try to recover
                log.warning(f"Unexpected Llama output (iteration {iteration+1}): {value[:200]}")
                # Nudge the model back on track
                scratchpad += "\nThought: I need to use a tool or provide a Final Answer.\n"

        raise RuntimeError(
            f"ReAct loop exceeded {MAX_ITERATIONS} iterations without a Final Answer"
        )

    # ── Public API (identical signatures to Claude version) ──────────────────
    
    async def get_quote(self, address: dict, items: list) -> dict:
        result = self.quote_agent.estimate(address, items)
        return {"cost_usd": float(result["cost_usd"])} 

    async def get_quote(self, address: dict, items: list) -> dict:
        """
        Estimate shipping cost using Llama 3 + ReAct.
        Returns: {"cost_usd": float}
        """
        task = (
            f"Task: Estimate the shipping cost.\n"
            f"Address: {json.dumps(address)}\n"
            f"Items: {json.dumps(items)}\n"
            f"Use the get_shipping_quote tool, then return: "
            f'Final Answer: {{"cost_usd": <number>}}'
        )

        raw = self._run_agent_loop(task)
        log.info(f"GetQuote agent response: {raw}")

        try:
            data = json.loads(raw)
            return {"cost_usd": float(data["cost_usd"])}
        except Exception:
            match = re.search(r"[\d]+\.?[\d]*", raw)
            cost = float(match.group()) if match else 5.0
            return {"cost_usd": cost}

    async def ship_order(self, address: dict, items: list) -> dict:
        """
        Orchestrate a full shipment using Llama 3 + ReAct:
        quote → carrier selection → tracking ID.
        Returns: {"tracking_id": str}
        """
        item_count = sum(i.get("quantity", 1) for i in items)
        task = (
            f"Task: Fulfill a shipping order step by step.\n"
            f"Address: {json.dumps(address)}\n"
            f"Items: {json.dumps(items)}\n"
            f"Total items: {item_count}\n\n"
            f"You MUST call these tools in order:\n"
            f"1. get_shipping_quote — to get the cost\n"
            f"2. select_carrier — using the cost and item count\n"
            f"3. generate_tracking_id — using the chosen carrier\n"
            f'Then return: Final Answer: {{"tracking_id": "<id>"}}'
        )

        raw = self._run_agent_loop(task)
        log.info(f"ShipOrder agent response: {raw}")

        try:
            data = json.loads(raw)
            return {"tracking_id": str(data["tracking_id"])}
        except Exception:
            return {"tracking_id": raw.strip()[:64] or "UNKNOWN-TRACKING-ID"}
