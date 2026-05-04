import logging 
from fastapi import APIRouter, HTTPException
from app.schemas import PaymentRequest
from app.graph import build_graph
from app.repository import get_transaction
from app.database import transactions_collection
from typing import Optional

router = APIRouter()
graph = build_graph()
logger = logging.getLogger("payment-agent")


@router.get("/health")
def health():
    logger.info("[API] /health called")
    return {"status": "ok", "service": "paymentagent"}


@router.post("/payment/charge")
async def charge(request: PaymentRequest):
    logger.info("[API] /payment/charge called")
    logger.info(f"[API] Request payload: {request.dict(exclude={'credit_card_number', 'credit_card_cvv'})}")
    result = graph.ainvoke({
        "query": request.query,
        "currency_code": request.currency_code,
        "units": request.units,
        "nanos": request.nanos,
        "credit_card_number": request.credit_card_number,
        "credit_card_cvv": request.credit_card_cvv,
        "credit_card_expiration_year": request.credit_card_expiration_year,
        "credit_card_expiration_month": request.credit_card_expiration_month,
        "result": {}
    })
    return result["result"]


@router.get("/payment/transaction/{transaction_id}")
async def get_tx(transaction_id: str):
    doc = await get_transaction(transaction_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return doc


@router.post("/clear_payments")
async def clear_payments():
    await transactions_collection.delete_many({})
    return {"status": "cleared"}


@router.get("/payment/transactions/count")
async def count_transactions(status: Optional[str] = None):
    query = {"status": status} if status else {}
    count = await transactions_collection.count_documents(query)
    return {"count": count}