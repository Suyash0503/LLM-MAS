from typing import List, Optional
from pydantic import BaseModel, Field


class AdAgentRequest(BaseModel):
    context_keys: List[str] = Field(default_factory=list)
    instruction: Optional[str] = None


class AdItem(BaseModel):
    redirect_url: str
    text: str


class AdAgentResponse(BaseModel):
    ads: List[AdItem]
    used_context_keys: List[str]
    reasoning: str