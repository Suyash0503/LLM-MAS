from pydantic import BaseModel
from typing import Any


class GovernanceRequest(BaseModel):
    checkout_response: dict[str, Any]
    traces: list[dict[str, Any]]