from __future__ import annotations

from .models import PriorityEvaluationRequest, PrioritySignal


WEIGHTS = {
    "anomaly_score": 0.25,
    "novelty_score": 0.15,
    "trust_inverse": 0.20,
    "graph_expansion": 0.15,
    "asset_criticality": 0.15,
    "campaign_likelihood": 0.10,
}


def compute_priority(req: PriorityEvaluationRequest) -> PrioritySignal:
    priority = (
        req.anomaly_score * WEIGHTS["anomaly_score"]
        + req.novelty_score * WEIGHTS["novelty_score"]
        + (100.0 - req.trust_score) * WEIGHTS["trust_inverse"]
        + req.graph_expansion * WEIGHTS["graph_expansion"]
        + req.asset_criticality * WEIGHTS["asset_criticality"]
        + req.campaign_likelihood * WEIGHTS["campaign_likelihood"]
    )
    priority = min(100.0, round(priority, 2))
    route = route_priority(priority, req)
    evidence = [
        f"anomaly={req.anomaly_score}",
        f"novelty={req.novelty_score}",
        f"trust_inverse={round(100.0 - req.trust_score, 2)}",
        f"campaign={req.campaign_likelihood}",
    ]
    if req.asset_criticality >= 80:
        evidence.append("asset criticality requires elevated routing")
    if req.campaign_likelihood >= 70:
        evidence.append("campaign likelihood keeps the request on deep path")
    confidence = min(0.97, round(0.45 + priority / 200.0 + req.campaign_likelihood / 500.0, 2))
    return PrioritySignal(
        entity_id=req.entity_id,
        priority_score=priority,
        route=route,
        confidence=confidence,
        evidence=evidence,
        trace_id=req.trace_id,
        correlation_id=req.correlation_id,
    )


def route_priority(priority: float, req: PriorityEvaluationRequest) -> str:
    if req.asset_criticality >= 80 and req.campaign_likelihood >= 65:
        return "sentinel_immediate_attention"
    if priority >= 70:
        return "deep_graph_reasoning"
    if priority >= 40:
        return "hybrid_analysis"
    return "fast_path"
