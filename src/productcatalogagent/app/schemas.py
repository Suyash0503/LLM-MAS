from pydantic import BaseModel
from typing import Optional, List, Any


class ProductCatalogRequest(BaseModel):
    query: str
    product_ids: Optional[List[str]] = None


class ProductCatalogResponse(BaseModel):
    mode: str
    action: str
    data: Any