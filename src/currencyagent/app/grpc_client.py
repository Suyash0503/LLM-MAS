import logging
import grpc
from app.config import CURRENCY_HOST, CURRENCY_PORT
from app.clients import demo_pb2
from app.clients import demo_pb2_grpc

logger = logging.getLogger(__name__)


class CurrencyGrpcClient:
    def __init__(self):
        target = f"{CURRENCY_HOST}:{CURRENCY_PORT}"
        logger.info(f"Connecting to CurrencyService gRPC at {target}")
        self.channel = grpc.insecure_channel(target)
        self.stub = demo_pb2_grpc.CurrencyServiceStub(self.channel)
        logger.info("CurrencyGrpcClient initialized")

    def _money_to_dict(self, money):
        return {
            "currency_code": money.currency_code,
            "units": money.units,
            "nanos": money.nanos
        }

    def get_supported_currencies(self):
        logger.info("Calling gRPC GetSupportedCurrencies")
        try:
            request = demo_pb2.Empty()
            response = self.stub.GetSupportedCurrencies(request)
            currencies = list(response.currency_codes)
            logger.info(f"GetSupportedCurrencies returned {len(currencies)} currencies")
            return currencies
        except grpc.RpcError as e:
            logger.error(f"gRPC error in GetSupportedCurrencies: {e.code()} - {e.details()}")
            raise

    def convert(self, currency_code: str, units: int, nanos: int, to_code: str):
        logger.info(f"Calling gRPC Convert: {units}.{nanos} {currency_code} -> {to_code}")
        try:
            request = demo_pb2.CurrencyConversionRequest(**{
                "from": demo_pb2.Money(
                    currency_code=currency_code,
                    units=units,
                    nanos=nanos
                ),
                "to_code": to_code
            })
            response = self.stub.Convert(request)
            result = self._money_to_dict(response)
            logger.info(f"Convert result: {result}")
            return result
        except grpc.RpcError as e:
            logger.error(f"gRPC error in Convert: {e.code()} - {e.details()}")
            raise