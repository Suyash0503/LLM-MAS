from datetime import datetime, timezone
from app.database import transactions_collection


async def save_transaction(
    transaction_id: str,
    currency_code: str,
    units: int,
    nanos: int,
    credit_card_last4: str,
    status: str = "success"
):
    doc = {
        "transaction_id": transaction_id,
        "currency_code": currency_code,
        "units": units,
        "nanos": nanos,
        "credit_card_last4": credit_card_last4,
        "status": status,
        "created_at": datetime.now(timezone.utc)
    }
    result = await transactions_collection.insert_one(doc)
    return str(result.inserted_id)


async def get_transaction(transaction_id: str):
    doc = await transactions_collection.find_one({"transaction_id": transaction_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc