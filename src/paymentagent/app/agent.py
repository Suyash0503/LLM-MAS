import logging 
from app.grpc_client import PaymentGrpcClient

client = PaymentGrpcClient()

logger = logging.getLogger("payment-agent")


class PaymentAgent:
    def run(self, query: str, currency_code: str = "USD", units: int = 0,
            nanos: int = 0, credit_card_number: str = "",
            credit_card_cvv: int = 0, credit_card_expiration_year: int = 0,
            credit_card_expiration_month: int = 0):
        
        logger.info(f"[PaymentAgent] Received query: {query}")
        logger.debug(f"[PaymentAgent] Input → currency={currency_code}, amount={units}.{nanos}")

        result = client.charge(
            currency_code=currency_code,
            units=units,
            nanos=nanos,
            credit_card_number=credit_card_number,
            credit_card_cvv=credit_card_cvv,
            credit_card_expiration_year=credit_card_expiration_year,
            credit_card_expiration_month=credit_card_expiration_month
        )

        logger.info("[PaymentAgent] Charge completed successfully")

        return {
            "mode": "agent",
            "action": "charge",
            "data": result
        }