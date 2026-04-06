from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
from app.agent import ProductCatalogAgent
from app.llm.qwen import get_qwen_llm


class CatalogState(TypedDict):
    query: str
    product_ids: Optional[List[str]]
    route: str
    result: dict


agent = ProductCatalogAgent()
llm = get_qwen_llm()


def classify_request(state: CatalogState):
    if state.get("product_ids"):
        state["route"] = "get_product"
        return state

    prompt = f"""
You are a router for a product catalog service.
Classify the user request into exactly one label:
- list_products
- search_products
- get_product

Rules:
- If user wants all items or full catalog, return list_products
- If user is looking for a product by words like sunglasses, mug, watch, return search_products
- If a product id is provided, return get_product

User query: {state['query']}

Return only one label.
""".strip()

    response = llm.invoke(prompt)
    label = response.content.strip().lower()

    if "list_products" in label:
        state["route"] = "list_products"
    elif "get_product" in label:
        state["route"] = "get_product"
    else:
        state["route"] = "search_products"

    return state


def run_agent(state: CatalogState):
    if state["route"] == "get_product":
        state["result"] = agent.run(query=state["query"], product_ids=state.get("product_ids"))
    elif state["route"] == "list_products":
        state["result"] = {
            "mode": "agent",
            "action": "list_products",
            "data": agent.run(query="list all products", product_ids=None)["data"]
        }
    else:
        state["result"] = {
            "mode": "agent",
            "action": "search_products",
            "data": agent.run(query=state["query"], product_ids=None)["data"]
        }

    return state


def build_graph():
    graph = StateGraph(CatalogState)
    graph.add_node("classify_request", classify_request)
    graph.add_node("run_agent", run_agent)

    graph.set_entry_point("classify_request")
    graph.add_edge("classify_request", "run_agent")
    graph.add_edge("run_agent", END)

    return graph.compile()