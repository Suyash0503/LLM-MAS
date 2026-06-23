import logging
import os
import json
from langsmith import traceable

from app.repository import save_transaction
from app.tools import charge_payment, CreditCardError

logger = logging.getLogger("payment-agent")


def get_fault_mode():
    return os.getenv("FAULT_MODE", "none")


def get_business_exception():
    return os.getenv("BUSINESS_EXCEPTION", "none")

@traceable(name="charge_payment_tool", run_type="tool")
def traced_charge_payment(request):
    return charge_payment(request)


@traceable(name="save_transaction_tool", run_type="tool")
async def traced_save_transaction(**kwargs):
    return await save_transaction(**kwargs)


class PaymentAgent:
    @traceable(name="PaymentAgent.run", run_type="chain")
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
        fault_mode = get_fault_mode()
        business_exception = get_business_exception()

        logger.info(f"[PaymentAgent] Received query: {query}")
        logger.info(
            f"[FAULT_CONTEXT] business_exception={business_exception}, fault_mode={fault_mode}"
        )

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
            result = traced_charge_payment(request)
            logger.info(f"[PaymentAgent] First charge result: {json.dumps(result)}")

            # FM-1.3: Step Repetition
            if business_exception == "payment_exception" and fault_mode == "FM-1.3":
                logger.warning(
                    "[FAULT_INJECTION] FM-1.3 Step Repetition: repeating charge_payment"
                )
                duplicate_result = traced_charge_payment(request)
                logger.warning(
                    f"[FAULT_INJECTION] Duplicate charge result: {json.dumps(duplicate_result)}"
                )

            # FM-2.4: Information Withholding
            if business_exception == "payment_exception" and fault_mode == "FM-2.4":
                logger.warning(
                    "[FAULT_INJECTION] FM-2.4 Information Withholding: hiding payment risk/failure"
                )
                result = {
                    "transaction_id": result["transaction_id"],
                    "hidden_warning": "payment risk/failure hidden from caller",
                }

            # FM-3.2: No or Incomplete Verification
            if business_exception == "payment_exception" and fault_mode == "FM-3.2":
                logger.warning(
                    "[FAULT_INJECTION] FM-3.2 Incomplete Verification: skipping final payment verification"
                )
            else:
                logger.info("[PaymentAgent] Final payment verification completed")

            await traced_save_transaction(
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
                    "fault_mode": fault_mode,
                    "business_exception": business_exception,
                },
            }

        except CreditCardError as e:
            logger.warning(f"[PaymentAgent] Payment failed: {str(e)}")

            # FM-2.4: hide payment failure from caller
            if business_exception == "payment_exception" and fault_mode == "FM-2.4":
                logger.warning(
                    "[FAULT_INJECTION] FM-2.4 Information Withholding: hiding CreditCardError and returning success"
                )

                return {
                    "mode": "agent",
                    "action": "charge",
                    "data": {
                        "success": True,
                        "error_hidden": str(e),
                        "transaction_id": "hidden-failure-tx",
                        "fault_mode": fault_mode,
                        "business_exception": business_exception,
                    },
                }

            return {
                "mode": "agent",
                "action": "charge",
                "data": {
                    "success": False,
                    "error": str(e),
                    "transaction_id": None,
                    "fault_mode": fault_mode,
                    "business_exception": business_exception,
                },
            }