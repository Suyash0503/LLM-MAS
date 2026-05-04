from fastapi import APIRouter, HTTPException

from app.graph import build_graph
from app.schemas import AdAgentRequest, AdAgentResponse

router = APIRouter()
ad_graph = build_graph()


@router.get("/health")
def health():
    return {"status": "ok", "service": "adserviceagent"}


@router.post("/ads", response_model=AdAgentResponse)
def get_ads(request: AdAgentRequest):
    try:
        result = ad_graph.invoke(
            {
                "instruction": request.instruction or "",
                "context_keys": request.context_keys or [],
            }
        )
        return result["final_response"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))