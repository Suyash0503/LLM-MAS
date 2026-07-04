from typing import Any


def durability_of_violation(traces: list[dict[str, Any]], window: int) -> int:
    """
    Durability means the maximum number of continuous trace events
    where violation=True inside the latest sliding window.
    """
    recent = traces[-window:] if len(traces) >= window else traces

    max_run = 0
    current_run = 0

    for event in recent:
        if event.get("violation", False):
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 0

    return max_run


def temporal_propagation(trace: dict[str, Any]) -> float:
    """
    TProp approximates whether the failure propagated downstream.
    Higher value means failure affected more dependent services/agents.
    """
    impacted_nodes = trace.get("impacted_nodes", [])
    dependency_nodes = trace.get("dependency_nodes", [])

    if not dependency_nodes:
        return 0.0

    return len(impacted_nodes) / len(dependency_nodes)


def mid_action_checkpoint(
    traces: list[dict[str, Any]],
    window: int = 5,
    g_mid: int = 2,
) -> dict[str, Any]:
    """
    Mid-action decision:
    if violation durability inside sliding window is >= g_mid,
    interrupt execution; otherwise continue.
    """
    dur = durability_of_violation(traces, window)

    decision = "Interrupt" if dur >= g_mid else "Continue"

    return {
        "checkpoint": "mid_action",
        "window": window,
        "g_mid": g_mid,
        "durability": dur,
        "decision": decision,
        "reason": (
            "Sustained live instability detected."
            if decision == "Interrupt"
            else "Violation did not persist long enough inside sliding window."
        ),
    }


def post_action_rejection_adjudication(
    trace: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Detect predicate-based false rejection.

    False rejection means the system rejected a migration/action,
    but post-action evidence shows the system was actually stable enough.
    """
    if thresholds is None:
        thresholds = {
            "qa_min": 0.85,
            "latency_max": 250.0,
            "slo_error_max": 0.05,
            "tprop_max": 0.20,
            "g_post": 2,
        }

    qa = trace.get("qa_score", 0.0)
    latency_p95 = trace.get("latency_p95_ms", 9999.0)
    slo_error = trace.get("slo_error_rate", 1.0)
    dur = trace.get("durability", 999)
    tprop = temporal_propagation(trace)

    false_rejection = (
        qa >= thresholds["qa_min"]
        and latency_p95 <= thresholds["latency_max"]
        and slo_error <= thresholds["slo_error_max"]
        and tprop <= thresholds["tprop_max"]
        and dur <= thresholds["g_post"]
    )

    decision = "Override Accept" if false_rejection else "Keep Rejection"

    return {
        "checkpoint": "post_action_rejection",
        "qa_score": qa,
        "latency_p95_ms": latency_p95,
        "slo_error_rate": slo_error,
        "temporal_propagation": round(tprop, 3),
        "durability": dur,
        "decision": decision,
        "false_rejection_detected": false_rejection,
    }


def post_action_complete_adjudication(
    trace: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Detect predicate-based false acceptance.

    False acceptance means the system accepted an action,
    but post-action evidence shows unstable behavior persisted.
    """
    if thresholds is None:
        thresholds = {
            "qa_min": 0.85,
            "latency_max": 250.0,
            "slo_error_max": 0.05,
            "g_post": 2,
        }

    qa = trace.get("qa_score", 1.0)
    latency_p95 = trace.get("latency_p95_ms", 0.0)
    slo_error = trace.get("slo_error_rate", 0.0)
    dur = trace.get("durability", 0)

    false_acceptance = (
        qa < thresholds["qa_min"]
        or latency_p95 > thresholds["latency_max"]
        or slo_error > thresholds["slo_error_max"]
        or dur > thresholds["g_post"]
    )

    decision = "Override Reject" if false_acceptance else "Confirm Accept"

    return {
        "checkpoint": "post_action_complete",
        "qa_score": qa,
        "latency_p95_ms": latency_p95,
        "slo_error_rate": slo_error,
        "durability": dur,
        "decision": decision,
        "false_acceptance_detected": false_acceptance,
    }


def infer_root_cause(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Finds the first failed event in the trace and uses it as root cause.
    """
    for event in traces:
        if event.get("status") in ["failed", "error", "timeout"]:
            return {
                "root_cause_node": event.get("node", "unknown"),
                "root_cause": event.get("message", "Unknown failure"),
                "failure_type": event.get("failure_type", "Unknown"),
                "timestamp": event.get("timestamp"),
            }

    return {
        "root_cause_node": "none",
        "root_cause": "No failure detected",
        "failure_type": "None",
        "timestamp": None,
    }


def verify(checkout_response: dict[str, Any], traces: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Full governance policy:
    runs mid-action checkpoint, then post-action adjudication.
    """
    mid = mid_action_checkpoint(traces)

    root = infer_root_cause(traces)

    final_trace = traces[-1] if traces else {}
    final_trace["durability"] = durability_of_violation(traces, window=5)

    checkout_status = checkout_response.get("status", "unknown")

    if checkout_status in ["rejected", "blocked", "failed"]:
        post = post_action_rejection_adjudication(final_trace)
    else:
        post = post_action_complete_adjudication(final_trace)

    return {
        "governance_policy": "two_tier_mid_action_and_post_action_adjudication",
        "mid_action_checkpoint": mid,
        "post_action_adjudication": post,
        "root_cause_annotation": root,
        "final_decision": post["decision"],
        "explanation": (
            "Mid-action checkpoint uses sliding-window durability of live violations. "
            "Post-action adjudication uses QA, latency, SLO error rate, temporal propagation, "
            "and violation durability to confirm or override the automated predicate verdict."
        ),
    }