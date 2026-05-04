using System.Collections.Concurrent;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Hipstershop;
using System.IO;

namespace cartservice;

/// <summary>
/// OllamaCartAgent wraps llama3.2:1b for cart reasoning.
///
/// Architecture decision:
///   llama3.2:1b does NOT support native tool/function calling, so we use a
///   structured prompt + strict JSON extraction pattern. Cart state is kept
///   in a thread-safe in-memory store (ConcurrentDictionary) so state is
///   always consistent regardless of LLM output quality.
///
///   The LLM is used for:
///     - Intent parsing / validation of unusual inputs
///     - Quantity merging logic (e.g. "add 2 more to existing 3")
///   The in-memory store is the source of truth for cart state.
/// </summary>
public class OllamaCartAgent
{
    private readonly HttpClient _http;
    private readonly ILogger<OllamaCartAgent> _logger;
    private readonly string _ollamaUrl;
    private readonly string _model;

    // Thread-safe in-memory cart store: userId -> (productId -> quantity)
    private readonly ConcurrentDictionary<string, ConcurrentDictionary<string, int>> _carts = new();

    private static readonly JsonSerializerOptions _jsonOpts = new()
    {
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    public OllamaCartAgent(HttpClient http, ILogger<OllamaCartAgent> logger, IConfiguration config)
    {
        _http = http;
        _logger = logger;
        _ollamaUrl = config["OLLAMA_URL"] ?? "http://ollama:11434";
        _model = config["OLLAMA_MODEL"] ?? "llama3.2:1b";
    }

    // -- Public cart operations ------------------------------------------------

    public Task AddItemAsync(string userId, string productId, int quantity)
    {
        var userCart = _carts.GetOrAdd(userId, _ => new ConcurrentDictionary<string, int>());

        // Merge quantities: ask Ollama what the new quantity should be
        var existingQty = userCart.GetValueOrDefault(productId, 0);
        var newQty = MergeQuantityWithAgent(userId, productId, existingQty, quantity).GetAwaiter().GetResult();

        userCart[productId] = newQty;
        _logger.LogInformation("Cart updated: userId={UserId}, productId={ProductId}, qty={Qty}", userId, productId, newQty);
        return Task.CompletedTask;
    }

    public Task<List<CartItem>> GetCartAsync(string userId)
    {
        var items = new List<CartItem>();
        if (_carts.TryGetValue(userId, out var userCart))
        {
            foreach (var (productId, qty) in userCart)
            {
                if (qty > 0)
                    items.Add(new CartItem { ProductId = productId, Quantity = qty });
            }
        }
        return Task.FromResult(items);
    }

    public Task EmptyCartAsync(string userId)
    {
        _carts.TryRemove(userId, out _);
        return Task.CompletedTask;
    }

    // -- Ollama integration ----------------------------------------------------

    /// <summary>
    /// Ask the LLM to resolve the correct merged quantity.
    /// Falls back to (existing + incoming) if LLM fails or returns garbage.
    /// </summary>
    private async Task<int> MergeQuantityWithAgent(string userId, string productId, int existingQty, int incomingQty)
    {
        // For the simple case there's no ambiguity - skip LLM overhead
        if (existingQty == 0)
            return incomingQty;

        var prompt = $"""
You are a shopping cart assistant. Return ONLY a JSON object, no explanation, no markdown.

Current cart state for user "{userId}":
  product_id: "{productId}", current_quantity: {existingQty}

The user is adding {incomingQty} more of this product.

Respond with exactly this JSON and nothing else:
{{"new_quantity": <integer>}}
""";

        try
        {
            var raw = await CallOllamaAsync(prompt);
            var qty = ExtractIntFromJson(raw, "new_quantity");
            if (qty.HasValue && qty.Value > 0)
            {
                _logger.LogDebug("Ollama merged quantity: {Qty}", qty.Value);
                return qty.Value;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Ollama quantity merge failed, using sum fallback");
        }

        // Fallback: simple sum
        return existingQty + incomingQty;
    }

    private async Task<string> CallOllamaAsync(string prompt)
    {
        var payload = new
        {
            model = _model,
            prompt,
            stream = false,
            options = new { temperature = 0.0, num_predict = 64 }
        };

        var json = JsonSerializer.Serialize(payload);
        using var content = new StringContent(json, Encoding.UTF8, "application/json");

        var url = $"{_ollamaUrl.TrimEnd('/')}/api/generate";
        _logger.LogDebug("Calling Ollama at {Url}", url);

        using var response = await _http.PostAsync(url, content);
        response.EnsureSuccessStatusCode();

        var body = await response.Content.ReadAsStringAsync();
        _logger.LogDebug("Ollama raw response: {Body}", body);

        // Ollama returns {"response": "...", ...}
        using var doc = JsonDocument.Parse(body);
var root = doc.RootElement;

// ✅ TOKEN EXTRACTION
int inputTokens = root.TryGetProperty("prompt_eval_count", out var promptEval)
    ? promptEval.GetInt32()
    : 0;

int outputTokens = root.TryGetProperty("eval_count", out var eval)
    ? eval.GetInt32()
    : 0;

int totalTokens = inputTokens + outputTokens;

//  PRINT (for terminal logs)
Console.WriteLine($"TOKEN_METRICS input={inputTokens} output={outputTokens} total={totalTokens}");

// FILE LOG (used by your experiment scripts)
File.AppendAllText("token_log.txt", totalTokens + Environment.NewLine);

// RETURN MODEL RESPONSE
if (root.TryGetProperty("response", out var resp))
    return resp.GetString() ?? string.Empty;

        return body;
    }

    // -- JSON parsing helpers (robust against LLM output noise) ---------------

    /// <summary>
    /// Extracts an integer value from a JSON key in potentially noisy LLM output.
    /// Handles: extra text before/after JSON, markdown code fences, single quotes.
    /// </summary>
    private static int? ExtractIntFromJson(string raw, string key)
    {
        if (string.IsNullOrWhiteSpace(raw)) return null;

        // Strip markdown fences
        raw = raw.Replace("```json", "").Replace("```", "").Trim();

        // Find outermost JSON object
        var start = raw.IndexOf('{');
        var end = raw.LastIndexOf('}');
        if (start < 0 || end <= start) return null;

        var jsonSlice = raw[start..(end + 1)];

        try
        {
            using var doc = JsonDocument.Parse(jsonSlice);
            if (doc.RootElement.TryGetProperty(key, out var val))
            {
                if (val.TryGetInt32(out var i)) return i;
                // Sometimes LLM wraps number in quotes
                if (val.ValueKind == JsonValueKind.String && int.TryParse(val.GetString(), out var si))
                    return si;
            }
        }
        catch (JsonException)
        {
            // Try normalising single quotes ? double quotes
            try
            {
                var normalised = jsonSlice.Replace('\'', '"');
                using var doc2 = JsonDocument.Parse(normalised);
                if (doc2.RootElement.TryGetProperty(key, out var val2))
                    if (val2.TryGetInt32(out var i)) return i;
            }
            catch { /* give up */ }
        }

        return null;
    }
}
