from fastapi import APIRouter
from app.schemas import RecommendationRequest, RecommendationResponse
from app.graph import build_graph

router = APIRouter()
graph = build_graph()


@router.get("/health")
def health():
    return {"status": "ok", "service": "recommendationagent"}


@router.post("/recommendations/query", response_model=RecommendationResponse)
def query_recommendations(request: RecommendationRequest):
    result = graph.invoke({
        "query": request.query or "",
        "user_id": request.user_id,
        "product_ids": request.product_ids,
        "route": "",
        "raw_result": {},
        "result": {},
    })
    return result["result"]