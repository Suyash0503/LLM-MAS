from fastapi import APIRouter
from app.schemas import ProductCatalogRequest
from app.graph import build_graph

router = APIRouter()
graph = build_graph()


@router.get("/health")
def health():
    return {"status": "ok", "service": "productcatalogagent"}


@router.post("/catalog/query")
def query_catalog(request: ProductCatalogRequest):
    result = graph.invoke({
        "query": request.query,
        "product_ids": request.product_ids,
        "result": {}
    })
    return result["result"]