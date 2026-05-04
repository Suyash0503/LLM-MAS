import logging
from fastapi import APIRouter, HTTPException
from app.schemas import CurrencyRequest
from app.graph import build_graph
 
logger = logging.getLogger(__name__)
 
router = APIRouter()
graph = build_graph()
 
 
@router.get("/health")
def health():
    logger.info("Health check requested")
    return {"status": "ok", "service": "currencyagent"}

@router.post("/currency/query")
def query_currency(request: CurrencyRequest):
    logger.info(f"POST /currency/query | query='{request.query}' | from={request.from_currency} to={request.to_currency} units={request.units}")
    try:
        result = graph.invoke({
            "query": request.query,
            "from_currency": request.from_currency,
            "to_currency": request.to_currency,
            "units": request.units,
            "nanos": request.nanos,
            "result": {}
        })
        logger.info(f"Query completed | action={result['result']['action']}")
        return result["result"]
    except Exception as e:
        logger.error(f"Error processing currency query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))