from __future__ import annotations

import time
from typing import Any

from .base import AgentResult


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _normalize_score(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1.0:
            numeric = numeric / 100.0 if numeric <= 100.0 else 1.0
        return _clamp(numeric)
    return None


def _extract_risk_signal(result: AgentResult) -> float:
    output = result.output or {}
    direct_signal = _normalize_score(output.get("risk_signal"))
    if direct_signal is not None:
        return direct_signal
    for candidate in (
        output.get("risk_level"),
        output.get("decision", {}).get("risk_level") if isinstance(output.get("decision"), dict) else None,
    ):
        if isinstance(candidate, (int, float)):
            return _clamp(float(candidate) / 5.0 if float(candidate) <= 5.0 else float(candidate))
    for candidate in (
        output.get("score"),
        output.get("blast_radius", {}).get("score") if isinstance(output.get("blast_radius"), dict) else None,
    ):
        score = _normalize_score(candidate)
        if score is not None:
            return score
    baseline = 0.35
    if result.requires_approval:
        baseline = max(baseline, 0.7)
    if output.get("blocked"):
        baseline = max(baseline, 0.82)
    if not result.success:
        baseline = max(0.2, baseline - 0.1)
    return baseline


def _extract_specialty(agent_id: str, task_type: str, output: dict[str, Any]) -> str:
    if agent_id == "ad":
        return "identity_graph" if "path" in str(output).lower() or "blast" in str(output).lower() else "directory_control"
    if agent_id == "decision":
        return "response_decision"
    if agent_id == "remediation":
        return "containment_planning"
    return task_type or "general"


def build_agent_signal(task: dict[str, Any], result: AgentResult) -> dict[str, Any]:
    output = result.output or {}
    risk_signal = _extract_risk_signal(result)
    approval_weight = 0.2 if result.requires_approval else 0.0
    success_weight = 0.1 if result.success else -0.1
    priority = _clamp(risk_signal + approval_weight + success_weight)
    uncertainty = _clamp(0.55 if result.requires_approval else 0.35)
    if output.get("decision", {}).get("advisory_only") if isinstance(output.get("decision"), dict) else False:
        uncertainty = max(uncertainty, 0.45)
    return {
        "schema_version": "v1",
        "event_type": "agent_signal",
        "timestamp": time.time(),
        "task_id": result.task_id,
        "event_id": result.task_id,
        "entity_id": task.get("entity_id"),
        "entity_type": task.get("entity_type"),
        "agent_id": result.agent_id,
        "specialty": _extract_specialty(result.agent_id, str(task.get("type", "")), output),
        "risk_signal": risk_signal,
        "priority": priority,
        "runtime_trust": _clamp(0.75 if result.success else 0.4),
        "uncertainty": uncertainty,
        "data_quality": _clamp(0.8 if output else 0.45),
        "reasoning_quality": _clamp(0.75 if result.reasoning else 0.3),
        "requires_approval": result.requires_approval,
        "success": result.success,
        "explanation": result.reasoning,
        "output": output,
    }
