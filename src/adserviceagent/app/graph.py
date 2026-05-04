from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

from app.agent import prepare_agent_input
from app.grpc_client import AdServiceClient


class AdAgentState(TypedDict, total=False):
    instruction: str
    context_keys: List[str]
    reasoning: str
    ads: List[Dict[str, Any]]
    final_response: Dict[str, Any]


def input_node(state: AdAgentState) -> AdAgentState:
    prepared = prepare_agent_input(state)
    state["instruction"] = prepared["instruction"]
    state["context_keys"] = prepared["context_keys"]
    state["reasoning"] = prepared["reasoning"]
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