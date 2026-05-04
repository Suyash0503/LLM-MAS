from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from app.agent import prepare_agent_input
from app.grpc_client import AdServiceClient
from app.llm.qwen import get_qwen_llm
import os

llm = get_qwen_llm()

class AdAgentState(TypedDict, total=False):
    instruction: str
    context_keys: List[str]
    reasoning: str
    ads: List[Dict[str, Any]]
    final_response: Dict[str, Any]


def input_node(state: AdAgentState) -> AdAgentState:
    prepared = prepare_agent_input(state)

    instruction = prepared["instruction"]

    # ✅ Only call LLM if enabled
    if os.getenv("USE_LLM", "false").lower() == "true":
        prompt = f"""
You are an ad selection assistant.

User request: {instruction}

Extract relevant ad categories from this request.
Return a comma separated list like:
electronics, clothing, footwear

Only return categories.
""".strip()

        response = llm.invoke(prompt)

        #  TOKEN LOGGING
        input_tokens = response.usage_metadata.get("input_tokens", 0)
        output_tokens = response.usage_metadata.get("output_tokens", 0)
        total_tokens = response.usage_metadata.get("total_tokens", 0)

        print(f"TOKEN_METRICS input={input_tokens} output={output_tokens} total={total_tokens}")

        with open("token_log.txt", "a") as f:
            f.write(f"{total_tokens}\n")

        categories = [c.strip() for c in response.content.lower().split(",")]

        state["context_keys"] = categories
        state["reasoning"] = "LLM-based category extraction"
    else:
        state["context_keys"] = prepared["context_keys"]
        state["reasoning"] = prepared["reasoning"]

    state["instruction"] = instruction

    return state


def ad_lookup_node(state: AdAgentState) -> AdAgentState:
    client = AdServiceClient()
    ads = client.get_ads(state.get("context_keys", []))
    state["ads"] = ads
    return state


def output_node(state: AdAgentState) -> AdAgentState:
    state["final_response"] = {
        "ads": state.get("ads", []),
        "used_context_keys": state.get("context_keys", []),
        "reasoning": state.get("reasoning", "Ad selection completed.")
    }
    return state


def build_graph():
    graph = StateGraph(AdAgentState)

    graph.add_node("input_node", input_node)
    graph.add_node("ad_lookup_node", ad_lookup_node)
    graph.add_node("output_node", output_node)

    graph.set_entry_point("input_node")
    graph.add_edge("input_node", "ad_lookup_node")
    graph.add_edge("ad_lookup_node", "output_node")
    graph.add_edge("output_node", END)

    return graph.compile()