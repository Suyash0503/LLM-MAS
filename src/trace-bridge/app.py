from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import subprocess
import uuid
import requests

app = FastAPI(title="Trace Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = r"C:\Users\suyas\ENGR6971"
REQUEST_JSON = r"C:\Users\suyas\ENGR6971\src\checkout-agent\checkout_request.json"
GOVERNANCE_URL = "http://localhost:8090/verify"


@app.post("/run-checkout-trace")
def run_checkout_trace():
    now = datetime.utcnow().isoformat() + "Z"
    trace_id = f"trace-{uuid.uuid4().hex[:8]}"

    traces = [
        {
            "id": 1,
            "timestamp": now,
            "title": "Request received",
            "node": "User / Frontend",
            "status": "success",
            "message": "Frontend triggered checkout trace.",
            "violation": False,
        },
        {
            "id": 2,
            "timestamp": now,
            "title": "Checkout orchestrator invoked",
            "node": "Checkout Orchestrator Agent",
            "status": "success",
            "message": "Trace Bridge invoked Checkout Agent through grpcurl.",
            "violation": False,
        },
    ]

    cmd = (
        f'Get-Content "{REQUEST_JSON}" -Raw | '
        f'grpcurl --% -plaintext -import-path .\\protos '
        f'-proto demo.proto -d @ localhost:5050 '
        f'hipstershop.CheckoutService/PlaceOrder'
    )

    result = subprocess.run(
        ["powershell", "-Command", cmd],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    output = result.stdout + result.stderr

    traces.append({
        "id": 3,
        "timestamp": now,
        "title": "Payment agent called",
        "node": "Payment Agent",
        "status": "success",
        "message": "Checkout attempted payment-related tool execution.",
        "violation": False,
    })

    failed = result.returncode != 0

    if failed:
        traces.append({
            "id": 4,
            "timestamp": now,
            "title": "Checkout/payment failure detected",
            "node": "Payment Service",
            "status": "timeout",
            "message": output[-500:],
            "failure_type": "Tool/API invocation failure",
            "violation": True,
            "qa_score": 0.60,
            "latency_p95_ms": 950,
            "slo_error_rate": 0.30,
            "impacted_nodes": ["Payment Agent", "Checkout Orchestrator"],
            "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
        })
    else:
        traces.append({
            "id": 4,
            "timestamp": now,
            "title": "Payment service completed",
            "node": "Payment Service",
            "status": "success",
            "message": "Checkout completed without payment failure.",
            "violation": False,
        })

    traces.append({
        "id": 5,
        "timestamp": now,
        "title": "Failure propagated",
        "node": "Checkout Orchestrator Agent",
        "status": "warning" if failed else "success",
        "message": "Checkout state evaluated after payment execution.",
        "violation": failed,
        "qa_score": 0.58 if failed else 0.95,
        "latency_p95_ms": 980 if failed else 130,
        "slo_error_rate": 0.34 if failed else 0.01,
        "impacted_nodes": ["Payment Agent", "Checkout Orchestrator"] if failed else [],
        "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
    })

    traces.append({
        "id": 6,
        "timestamp": now,
        "title": "Governance validation",
        "node": "Governance Agent",
        "status": "blocked" if failed else "success",
        "message": "Governance Agent verifies trace evidence.",
        "violation": failed,
        "qa_score": 0.57 if failed else 0.96,
        "latency_p95_ms": 990 if failed else 120,
        "slo_error_rate": 0.35 if failed else 0.01,
        "impacted_nodes": ["Payment Agent", "Checkout Orchestrator", "User"] if failed else [],
        "dependency_nodes": ["User", "Checkout", "Payment Agent", "Payment Service"],
    })

    checkout_response = {
        "status": "blocked" if failed else "accepted",
        "order_created": not failed,
        "reason": "runtime_failure_detected" if failed else "checkout_completed",
    }

    governance_result = requests.post(
    GOVERNANCE_URL,
    json={"checkout_response": checkout_response, "traces": traces},
    timeout=5,
).json()

    if "shippingservice: no such host" in output:
        root_cause = "Shipping Service"
        failure_type = "gRPC dependency resolution failure"
        propagation_path = "Shipping Service → Shipping Agent → Checkout Orchestrator → User"
    elif "paymentservice" in output.lower():
        root_cause = "Payment Service"
        failure_type = "Payment service timeout"
        propagation_path = "Payment Service → Payment Agent → Checkout Orchestrator → User"
    else:
        root_cause = governance_result["root_cause_annotation"]["root_cause_node"]
        failure_type = governance_result["root_cause_annotation"]["failure_type"]
        propagation_path = "Payment Service → Payment Agent → Checkout Orchestrator → User"

    return {
        "trace_id": trace_id,
        "scenario": "Runtime checkout trace through grpcurl bridge",
        "checkout_output": output,
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
            "root_cause": root_cause,
            "failure_type": failure_type,
            "propagation_path": propagation_path,
            "system_effect": "Order creation blocked" if failed else "Order completed",
            "governance_decision": governance_result["final_decision"],
            "mid_action_decision": governance_result["mid_action_checkpoint"]["decision"],
            "durability": governance_result["mid_action_checkpoint"]["durability"],
        },
        "governance_result": governance_result,
    }