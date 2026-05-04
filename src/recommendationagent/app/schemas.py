from pydantic import BaseModel, Field
from typing import Optional, List, Any


class RecommendationRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user to get recommendations for")
    product_ids: List[str] = Field(..., description="Products currently in cart or being viewed")
    query: Optional[str] = Field(
        default="",
        description="Optional natural-language query (e.g. 'explain why these are recommended')",
    )


class RecommendationResponse(BaseModel):
    mode: str
    action: str
    user_id: str
    input_product_ids: List[str]
    recommended_product_ids: List[str]
    explanation: Optional[str] = None