from typing import Dict, Any, List


KEYWORD_MAP = {
    "clothing": ["clothing", "fashion", "shirt", "dress", "jacket", "wear"],
    "accessories": ["accessories", "watch", "bag", "wallet"],
    "footwear": ["shoe", "shoes", "footwear", "sneakers"],
    "kitchen": ["kitchen", "cookware", "utensils", "cooking"],
    "electronics": ["electronics", "gadget", "gadgets", "tech", "phone", "laptop"],
    "general": ["general", "random", "anything"]
}


def extract_context_from_instruction(instruction: str) -> List[str]:
    instruction = (instruction or "").lower()
    found = []

    for category, keywords in KEYWORD_MAP.items():
        if any(word in instruction for word in keywords):
            found.append(category)

    if not found:
        found.append("general")

    # remove duplicates while preserving order
    seen = set()
    ordered = []
    for item in found:
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    return ordered


def build_reasoning(context_keys: List[str], instruction: str) -> str:
    if context_keys:
        return f"Selected ad categories based on request context: {', '.join(context_keys)}."
    if instruction:
        return "Selected ad categories by interpreting the natural language instruction."
    return "No specific context provided; used fallback general ad category."


def prepare_agent_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    instruction = payload.get("instruction") or ""
    context_keys = payload.get("context_keys") or []

    if not context_keys and instruction:
        context_keys = extract_context_from_instruction(instruction)

    if not context_keys:
        context_keys = ["general"]

    reasoning = build_reasoning(context_keys, instruction)

    return {
        "instruction": instruction,
        "context_keys": context_keys,
        "reasoning": reasoning,
    }