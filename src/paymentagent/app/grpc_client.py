import grpc
import logging 
from fastapi import HTTPException
from app.config import PAYMENT_HOST, PAYMENT_PORT
from app.clients import demo_pb2
from app.clients import demo_pb2_grpc

logger = logging.getLogger("payment-agent")

class PaymentGrpcClient:
    def __init__(self):
        target = f"{PAYMENT_HOST}:{PAYMENT_PORT}"
        self.channel = grpc.insecure_channel(target)
        self.stub = demo_pb2_grpc.PaymentServiceStub(self.channel)

    def _charge_to_dict(self, response):
        return {
            "transaction_id": response.transaction_id
        }

    def charge(self, currency_code: str, units: int, nanos: int,
               credit_card_number: str, credit_card_cvv: int,
               credit_card_expiration_year: int, credit_card_expiration_month: int):
        
        logger.info(f"[PaymentService] Charge request → {currency_code} {units}.{nanos}")

        try:
            request = demo_pb2.ChargeRequest(
                amount=demo_pb2.Money(
                    currency_code=currency_code,
                    units=units,
                    nanos=nanos
                ),
                credit_card=demo_pb2.CreditCardInfo(
                    credit_card_number=credit_card_number,
                    credit_card_cvv=credit_card_cvv,
                    credit_card_expiration_year=credit_card_expiration_year,
                    credit_card_expiration_month=credit_card_expiration_month
                )
            )
            logger.info(f"[PaymentService] Sending gRPC request to {PAYMENT_HOST}:{PAYMENT_PORT}")

            response = self.stub.Charge(request, timeout=5)

            logger.info(f"[PaymentService] Charge success → transaction_id={response.transaction_id}")

            return self._charge_to_dict(response)

        except grpc.RpcError as e:
            logger.error(f"[PaymentService] gRPC error → code={e.code()} message={e.details()}")
            msg = e.details() or "payment service error"

            if e.code() == grpc.StatusCode.UNAVAILABLE:
                raise HTTPException(status_code=503, detail="payment gRPC service unavailable")
            elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                raise HTTPException(status_code=504, detail="payment request timed out")
            elif e.code() == grpc.StatusCode.INVALID_ARGUMENT:
                raise HTTPException(status_code=400, detail=msg)
            else:
                raise HTTPException(status_code=400, detail=msg)