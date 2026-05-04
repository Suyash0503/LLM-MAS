import uuid
from datetime import datetime
import re


# -----------------------------
# Custom Errors (match baseline)
# -----------------------------
class CreditCardError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.code = 400


class InvalidCreditCard(CreditCardError):
    def __init__(self):
        super().__init__("Credit card info is invalid")


class UnacceptedCreditCard(CreditCardError):
    def __init__(self, card_type):
        super().__init__(
            f"Sorry, we cannot process {card_type} credit cards. Only VISA or MasterCard is accepted."
        )


class ExpiredCreditCard(CreditCardError):
    def __init__(self, number, month, year):
        super().__init__(
            f"Your credit card (ending {number[-4:]}) expired on {month}/{year}"
        )


# -----------------------------
# Helper: detect card type
# -----------------------------
def get_card_type(number: str):
    number = number.replace("-", "").replace(" ", "")

    if re.match(r"^4", number):
        return "visa"
    if re.match(r"^5[1-5]", number):
        return "mastercard"
    if re.match(r"^3[47]", number):
        return "amex"

    return "unknown"


# -----------------------------
# Helper: basic validity check
# -----------------------------
def is_valid_card(number: str):
    number = number.replace("-", "").replace(" ", "")
    return number.isdigit() and len(number) >= 12


# -----------------------------
# MAIN TOOL (baseline logic)
# -----------------------------
def charge_payment(request: dict):
    amount = request.get("amount", {})
    credit_card = request.get("credit_card", {})

    card_number = credit_card.get("credit_card_number", "")

    # ---- validate card ----
    if not is_valid_card(card_number):
        raise InvalidCreditCard()

    card_type = get_card_type(card_number)

    # ---- only VISA / MasterCard ----
    if card_type not in ["visa", "mastercard"]:
        raise UnacceptedCreditCard(card_type)

    # ---- expiry check (same formula as baseline) ----
    current_month = datetime.now().month
    current_year = datetime.now().year

    year = credit_card.get("credit_card_expiration_year", 0)
    month = credit_card.get("credit_card_expiration_month", 0)

    if (current_year * 12 + current_month) > (year * 12 + month):
        raise ExpiredCreditCard(card_number.replace("-", ""), month, year)

    # ---- SUCCESS ----
    return {
        "transaction_id": str(uuid.uuid4())
    }