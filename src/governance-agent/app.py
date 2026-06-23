from fastapi import FastAPI

from models import GovernanceRequest
from verifier import verify

app = FastAPI()


@app.post("/verify")
def verify_order(req: GovernanceRequest):
    return verify(
        req.checkout_response,
        req.traces,
    )