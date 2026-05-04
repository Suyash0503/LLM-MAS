import logging
from app.repository import save_transaction
from app.tools import charge_payment, CreditCardError

logger = logging.getLogger("payment-agent")


class PaymentAgent:
    async def run(
        self,
        query: str,
        currency_code: str = "USD",
        units: int = 0,
        nanos: int = 0,
        credit_card_number: str = "",
        credit_card_cvv: int = 0,
        credit_card_expiration_year: int = 0,
        credit_card_expiration_month: int = 0,
    ):
        logger.info(f"[PaymentAgent] Received query: {query}")

        request = {
            "amount": {
                "currency_code": currency_code,
                "units": units,
                "nanos": nanos,
            },
            "credit_card": {
                "credit_card_number": credit_card_number,
                "credit_card_cvv": credit_card_cvv,
                "credit_card_expiration_year": credit_card_expiration_year,
                "credit_card_expiration_month": credit_card_expiration_month,
            },
        }

        try:
            result = charge_payment(request)

            await save_transaction(
                transaction_id=result["transaction_id"],
                currency_code=currency_code,
                units=units,
                nanos=nanos,
                credit_card_last4=credit_card_number[-4:] if credit_card_number else "****",
                status="success",
            )

            return {
                "mode": "agent",
                "action": "charge",
                "data": {
                    "success": True,
                    "transaction_id": result["transaction_id"],
                },
            }

        except CreditCardError as e:
            logger.warning(f"[PaymentAgent] Payment failed: {str(e)}")

            return {
                "mode": "agent",
                "action": "charge",
                "data": {
                    "success": False,
                    "error": str(e),
                    "transaction_id": None,
                },
            }