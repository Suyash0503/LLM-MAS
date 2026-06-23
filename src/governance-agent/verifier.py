def verify(checkout_response, traces):
    text = str(checkout_response)

    if '"type":"function"' in text or "quote_shipping" in text:
        return {
            "decision": "reject",
            "mast_mode": "FM-1.3",
            "reason": "LLM leaked tool-call/schema JSON instead of final order JSON"
        }

    return {
        "decision": "approve",
        "mast_mode": None,
        "reason": "No governance violation detected"
    }