from pydantic import BaseModel


class GovernanceRequest(BaseModel):
    checkout_response: dict
    traces: list[dict]