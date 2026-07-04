from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid

from models import GovernanceRequest
from verifier import verify


app = FastAPI(title="Governance Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/verify")
def verify_order(req: GovernanceRequest):
    return verify(
        req.checkout_response,
        req.traces,
    )


@app.get("/trace/payment-timeout")
def payment_timeout_trace():
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow().isoformat() + "Z"

    traces = [
        {
            "id": 1,
            "timestamp": now,
            "title": "Request received",
            "node": "User / Frontend",
            "status": "success",
            "message": "Checkout request entered the system.",
            "violation": False,
            "qa_score": 0.95,
            "latency_p95_ms": 120,
            "slo_error_rate": 0.01,
            "impacted_nodes": [],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        },
        {
            "id": 2,
            "timestamp": now,
            "title": "Checkout orchestrator invoked",
            "node": "Checkout Orchestrator Agent",
            "status": "success",
            "message": "Checkout workflow started.",
            "violation": False,
            "qa_score": 0.94,
            "latency_p95_ms": 130,
            "slo_error_rate": 0.01,
            "impacted_nodes": [],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        },
        {
            "id": 3,
            "timestamp": now,
            "title": "Payment agent called",
            "node": "Payment Agent",
            "status": "success",
            "message": "Payment authorization delegated to Payment Agent.",
            "violation": False,
            "qa_score": 0.93,
            "latency_p95_ms": 160,
            "slo_error_rate": 0.02,
            "impacted_nodes": [],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        },
        {
            "id": 4,
            "timestamp": now,
            "title": "Payment service timeout",
            "node": "Payment Service",
            "status": "timeout",
            "message": "Payment Service did not respond within timeout window.",
            "failure_type": "Tool/API invocation failure",
            "violation": True,
            "qa_score": 0.60,
            "latency_p95_ms": 950,
            "slo_error_rate": 0.30,
            "impacted_nodes": ["Payment Agent"],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        },
        {
            "id": 5,
            "timestamp": now,
            "title": "Failure propagated",
            "node": "Checkout Orchestrator Agent",
            "status": "warning",
            "message": "Checkout cannot safely complete because payment state is unknown.",
            "violation": True,
            "qa_score": 0.58,
            "latency_p95_ms": 980,
            "slo_error_rate": 0.34,
            "impacted_nodes": ["Payment Agent", "Checkout Orchestrator"],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        },
        {
            "id": 6,
            "timestamp": now,
            "title": "Governance validation",
            "node": "Governance Agent",
            "status": "blocked",
            "message": "Governance Agent blocks order creation and records root cause.",
            "violation": True,
            "qa_score": 0.57,
            "latency_p95_ms": 990,
            "slo_error_rate": 0.35,
            "impacted_nodes": ["Payment Agent", "Checkout Orchestrator", "User"],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        },
    ]

    checkout_response = {
        "status": "blocked",
        "reason": "payment_state_unknown",
        "order_created": False,
    }

    governance_result = verify(checkout_response, traces)

    return {
        "trace_id": trace_id,
        "timestamp": now,
        "scenario": "Payment timeout during checkout",
        "failure_mode": "Tool Invocation Timeout",
        "checkout_response": checkout_response,
        "steps": [
            {
                "id": t["id"],
                "title": t["title"],
                "node": t["node"],
                "status": "failed" if t["status"] == "timeout" else t["status"],
                "detail": t["message"],
            }
            for t in traces
        ],
        "analysis": {
            "root_cause": governance_result["root_cause_annotation"]["root_cause_node"],
            "failure_type": governance_result["root_cause_annotation"]["failure_type"],
            "propagation_path": "Payment Service → Payment Agent → Checkout Orchestrator → User",
            "system_effect": "Order creation blocked",
            "governance_decision": governance_result["final_decision"],
            "mid_action_decision": governance_result["mid_action_checkpoint"]["decision"],
            "durability": governance_result["mid_action_checkpoint"]["durability"],
        },
        "governance_result": governance_result,
    }