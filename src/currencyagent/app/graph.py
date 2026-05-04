import logging
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from app.agent import CurrencyAgent
from app.llm.llama import get_llama_llm

logger = logging.getLogger(__name__)


class CurrencyState(TypedDict):
    query: str
    from_currency: Optional[str]
    to_currency: Optional[str]
    units: Optional[int]
    nanos: Optional[int]
    route: str
    result: dict


agent = CurrencyAgent()
llm = get_llama_llm()


def classify_request(state: CurrencyState):
    logger.info(f"classify_request called | query='{state['query']}'")

    prompt = f"""
You are a router for a currency service.
Classify the user request into exactly one label:
- get_supported_currencies
- convert

Rules:
- If user wants to know which currencies are available or supported, return get_supported_currencies
- If user wants to convert an amount from one currency to another, return convert

User query: {state['query']}

Return only one label.
""".strip()

    logger.debug("Invoking LLM for classification")
    response = llm.invoke(prompt)
    label = response.content.strip().lower()
    logger.info(f"LLM classification result: '{label}'")

    if "get_supported_currencies" in label:
        state["route"] = "get_supported_currencies"
    else:
        state["route"] = "convert"

    logger.info(f"Routing to: {state['route']}")
    return state


def run_agent(state: CurrencyState):
    logger.info(f"run_agent called | route={state['route']}")

    if state["route"] == "get_supported_currencies":
        state["result"] = agent.run(
            query=state["query"],
            action="get_supported_currencies"
        )
    else:
        state["result"] = agent.run(
            query=state["query"],
            action="convert",
            from_currency=state.get("from_currency", "USD"),
            units=state.get("units", 0),
            nanos=state.get("nanos", 0),
            to_currency=state.get("to_currency", "EUR")
        )

    logger.info(f"run_agent completed | action={state['result']['action']}")
    return state


def build_graph():
    logger.info("Building LangGraph for CurrencyAgent")
    graph = StateGraph(CurrencyState)
    graph.add_node("classify_request", classify_request)
    graph.add_node("run_agent", run_agent)

    graph.set_entry_point("classify_request")
    graph.add_edge("classify_request", "run_agent")
    graph.add_edge("run_agent", END)

    logger.info("LangGraph compiled successfully")
    return graph.compile()