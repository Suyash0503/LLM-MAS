import logging
from app.grpc_client import CurrencyGrpcClient

logger = logging.getLogger(__name__)

client = CurrencyGrpcClient()


class CurrencyAgent:
    def run(self, query: str, action: str = "get_supported_currencies",
            from_currency: str = "USD", units: int = 0,
            nanos: int = 0, to_currency: str = "EUR"):

        logger.info(f"CurrencyAgent.run called | action={action} | query='{query}'")
        q = query.lower().strip()

        if action == "convert" or "convert" in q or "to" in q:
            logger.info(f"Executing convert: {units}.{nanos} {from_currency} -> {to_currency}")
            result = {
                "mode": "agent",
                "action": "convert",
                "data": client.convert(
                    currency_code=from_currency,
                    units=units,
                    nanos=nanos,
                    to_code=to_currency
                )
            }
            logger.info(f"Convert completed: {result['data']}")
            return result

        logger.info("Executing get_supported_currencies")
        result = {
            "mode": "agent",
            "action": "get_supported_currencies",
            "data": client.get_supported_currencies()
        }
        logger.info(f"get_supported_currencies completed: {len(result['data'])} currencies returned")
        return result