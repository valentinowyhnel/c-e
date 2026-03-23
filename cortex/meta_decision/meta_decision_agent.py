from __future__ import annotations

import time
from dataclasses import dataclass

from .analysis_fingerprint_engine import AnalysisFingerprintEngine
from .analysis_reuse_orchestrator import AnalysisReuseOrchestrator
from .case_complexity_engine import CaseComplexityEngine
from .case_memory_store import CaseMemoryStore
from .confidence_calibration import ConfidenceCalibrationLayer
from .decision_memory_linker import DecisionMemoryLinker
from .decision_trust_engine import DecisionTrustEngine
from .deep_analysis_protocol import DeepAnalysisProtocol


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class MetaDecisionResult:
    weighted_scores: dict[str, float]
    agent_trust_scores: dict[str, float]
    conflict_score: float
    selected_agents: list[str]
    deep_analysis_triggered: bool
    reasoning_summary: str
    trust_matrix: dict[str, dict[str, float]]
    deep_analysis_requests: list[dict[str, object]]
    trusted_agent_output: dict[str, object]
    audit_log: dict[str, object]
    reuse_context: dict[str, object] | None = None
    degraded_mode: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "weighted_scores": dict(self.weighted_scores),
            "agent_trust_scores": dict(self.agent_trust_scores),
            "conflict_score": self.conflict_score,
            "selected_agents": list(self.selected_agents),
            "deep_analysis_triggered": self.deep_analysis_triggered,
            "reasoning_summary": self.reasoning_summary,
            "trust_matrix": {name: dict(values) for name, values in self.trust_matrix.items()},
            "deep_analysis_requests": list(self.deep_analysis_requests),
            "trusted_agent_output": dict(self.trusted_agent_output),
            "audit_log": dict(self.audit_log),
            "reuse_context": dict(self.reuse_context or {}),
            "degraded_mode": self.degraded_mode,
        }


class MetaDecisionAgent:
    def __init__(
        self,
        *,
        decision_trust_engine: DecisionTrustEngine,
        case_complexity_engine: CaseComplexityEngine | None = None,
        deep_analysis_protocol: DeepAnalysisProtocol | None = None,
        confidence_calibration: ConfidenceCalibrationLayer | None = None,
        decision_memory_linker: DecisionMemoryLinker | None = None,
        timeout_ms: int = 25,
        min_trust_threshold: float = 0.45,
    ) -> None:
        self.decision_trust_engine = decision_trust_engine
        self.case_complexity_engine = case_complexity_engine or CaseComplexityEngine()
        self.deep_analysis_protocol = deep_analysis_protocol or DeepAnalysisProtocol()
        self.confidence_calibration = confidence_calibration or ConfidenceCalibrationLayer()
        self.decision_memory_linker = decision_memory_linker or DecisionMemoryLinker(
            fingerprint_engine=AnalysisFingerprintEngine(),
            case_memory_store=CaseMemoryStore(),
            reuse_orchestrator=AnalysisReuseOrchestrator(),
        )
        self.timeout_ms = timeout_ms
        self.min_trust_threshold = min_trust_threshold

    @staticmethod
    def _extract_numeric_signal(message: dict[str, object]) -> float:
        return _clamp(float(message.get("risk_signal", message.get("score", 0.0))))

    def _compute_conflict(self, messages: list[dict[str, object]]) -> float:
        if len(messages) < 2:
            return 0.0
        signals = [self._extract_numeric_signal(message) for message in messages]
        spread = max(signals) - min(signals)
        mean_signal = sum(signals) / len(signals)
        disagreement = sum(abs(signal - mean_signal) for signal in signals) / len(signals)
        return _clamp(0.6 * spread + 0.4 * disagreement)

    def _build_weighted_scores(
        self,
        messages: list[dict[str, object]],
        agent_trust_scores: dict[str, float],
    ) -> tuple[dict[str, float], list[str]]:
        weighted_total = 0.0
        trust_total = 0.0
        weighted_scores: dict[str, float] = {}
        selected_agents: list[str] = []
        for message in messages:
            agent_id = str(message["sender"])
            trust = agent_trust_scores.get(agent_id, 0.0)
            if trust < self.min_trust_threshold:
                continue
            signal = self._extract_numeric_signal(message)
            weighted_total += signal * trust
            trust_total += trust
            selected_agents.append(agent_id)
        weighted_scores["aggregate_risk"] = _clamp(weighted_total / trust_total) if trust_total else 0.0
        for message in messages:
            agent_id = str(message["sender"])
            weighted_scores[f"{agent_id}_risk"] = _clamp(self._extract_numeric_signal(message) * agent_trust_scores.get(agent_id, 0.0))
        return weighted_scores, selected_agents

    def evaluate(
        self,
        *,
        event: dict[str, object],
        agent_messages: list[dict[str, object]],
        model_scores: dict[str, float] | None = None,
        identity_context: dict[str, object] | None = None,
        graph_context: dict[str, object] | None = None,
        policy_version: str = "opa:v1",
        model_versions: dict[str, str] | None = None,
    ) -> MetaDecisionResult:
        started = time.monotonic()
        audit_log: dict[str, object] = {
            "event_id": event.get("event_id"),
            "agent_count": len(agent_messages),
            "timestamp": event.get("timestamp"),
            "model_scores_present": bool(model_scores),
            "identity_context_present": bool(identity_context),
        }
        try:
            trust_inputs = []
            for message in agent_messages:
                trust_inputs.append(
                    {
                        "agent_id": message["sender"],
                        "specialty": message.get("specialty"),
                        "runtime_trust": float(message.get("runtime_trust", 0.5)),
                        "uncertainty": float(message.get("uncertainty", 1.0 - self._extract_numeric_signal(message))),
                        "data_quality": float(message.get("data_quality", 0.5)),
                        "reasoning_quality": float(message.get("reasoning_quality", 0.5)),
                    }
                )
            trust_computation = self.decision_trust_engine.compute_batch(trust_inputs)
            calibrated_scores = self.confidence_calibration.calibrate(
                trust_computation.agent_case_trust,
                trust_computation.trust_matrix,
            )
            conflict_score = self._compute_conflict(agent_messages)
            criticality = _clamp(
                0.55 * float(event.get("asset_criticality", 0.0))
                + 0.30 * float(event.get("blast_radius", 0.0))
                + 0.15 * float(bool(event.get("metadata", {}).get("crown_jewel", False)))
            )
            memory_context = self.decision_memory_linker.link(
                event=event,
                features=model_scores or {},
                graph_context=graph_context or identity_context or {},
                trust_context=trust_computation.agent_case_trust,
                novelty_score=float(event.get("novelty_score", 0.0)),
                criticality=criticality,
                policy_version=policy_version,
                model_versions=model_versions or {},
                event_flags={
                    "zero_day_possible": bool(event.get("metadata", {}).get("zero_day_possible", False)),
                    "admin_compromise": bool(event.get("metadata", {}).get("admin_compromise", False)),
                    "insider": bool(event.get("metadata", {}).get("insider", False)),
                    "crown_jewel": bool(event.get("metadata", {}).get("crown_jewel", False)),
                },
            )
            complexity = self.case_complexity_engine.assess(
                novelty_score=float(event.get("novelty_score", 0.0)),
                graph_depth=float(event.get("graph_score", 0.0)),
                temporal_span=float(event.get("temporal_score", 0.0)),
                conflict_score=conflict_score,
                criticality=criticality,
            )
            min_trust = min(calibrated_scores.values(), default=0.0)
            deep_analysis_reasons = []
            if conflict_score >= 0.55:
                deep_analysis_reasons.append("agent_conflict")
            if min_trust < self.min_trust_threshold:
                deep_analysis_reasons.append("low_agent_trust")
            if float(event.get("novelty_score", 0.0)) >= 0.7:
                deep_analysis_reasons.append("high_novelty")
            if criticality >= 0.75:
                deep_analysis_reasons.append("critical_asset")
            if memory_context.reuse.reuse_decision == "NO_REUSE" and memory_context.matching_cases:
                deep_analysis_reasons.append("reuse_rejected")
            deep_analysis_triggered = complexity.deep_analysis_required and bool(deep_analysis_reasons)
            weighted_scores, selected_agents = self._build_weighted_scores(agent_messages, calibrated_scores)
            if model_scores:
                weighted_scores["model_blend"] = _clamp(sum(model_scores.values()) / max(1, len(model_scores)))
            if memory_context.reuse.reuse_decision in {"FULL_REUSE", "PARTIAL_REUSE"}:
                matched_case = memory_context.reuse.matched_case or {}
                reused_scores = matched_case.get("scores", {})
                weighted_scores["reused_risk"] = _clamp(float(reused_scores.get("aggregate_risk", 0.0)))
                weighted_scores["aggregate_risk"] = _clamp(
                    0.7 * weighted_scores.get("aggregate_risk", 0.0)
                    + 0.3 * weighted_scores["reused_risk"]
                )
                selected_agents = [
                    agent_id for agent_id in selected_agents if agent_id not in memory_context.reuse.agents_to_bypass
                ]
            if weighted_scores.get("aggregate_risk", 0.0) == 0.0 and agent_messages:
                weighted_scores["aggregate_risk"] = _clamp(
                    sum(self._extract_numeric_signal(message) for message in agent_messages) / len(agent_messages)
                )
            deep_analysis_requests = []
            if deep_analysis_triggered:
                requests = self.deep_analysis_protocol.build_requests(
                    event_id=str(event.get("event_id")),
                    agent_ids=selected_agents or [str(message["sender"]) for message in agent_messages],
                    reasons=deep_analysis_reasons,
                )
                deep_analysis_requests = [request.to_dict() for request in requests]
            reasoning_summary = (
                f"path={complexity.complexity_level} conflict={conflict_score:.3f} "
                f"min_trust={min_trust:.3f} selected={len(selected_agents)}"
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            audit_log.update(
                {
                    "elapsed_ms": elapsed_ms,
                    "complexity_level": complexity.complexity_level,
                    "complexity_score": complexity.score,
                    "triggers": complexity.triggers,
                    "deep_analysis_reasons": deep_analysis_reasons,
                    "reuse_decision": memory_context.reuse.reuse_decision,
                    "reuse_confidence": memory_context.reuse.reuse_confidence,
                    "fingerprint": memory_context.fingerprint,
                }
            )
            degraded = elapsed_ms > self.timeout_ms
            if degraded:
                weighted_scores["aggregate_risk"] = _clamp(
                    sum(self._extract_numeric_signal(message) for message in agent_messages) / max(1, len(agent_messages))
                )
                selected_agents = [str(message["sender"]) for message in agent_messages]
                deep_analysis_requests = []
                deep_analysis_triggered = False
                reasoning_summary = "degraded_mode_timeout"
            trusted_agent_output = {
                "weighted_scores": weighted_scores,
                "agent_trust_scores": calibrated_scores,
                "conflict_score": conflict_score,
                "selected_agents": selected_agents,
                "deep_analysis_triggered": deep_analysis_triggered,
                "reasoning_summary": reasoning_summary,
                "reuse_decision": memory_context.reuse.reuse_decision,
            }
            return MetaDecisionResult(
                weighted_scores=weighted_scores,
                agent_trust_scores=calibrated_scores,
                conflict_score=conflict_score,
                selected_agents=selected_agents,
                deep_analysis_triggered=deep_analysis_triggered,
                reasoning_summary=reasoning_summary,
                trust_matrix=trust_computation.trust_matrix,
                deep_analysis_requests=deep_analysis_requests,
                trusted_agent_output=trusted_agent_output,
                audit_log=audit_log,
                reuse_context=memory_context.to_dict(),
                degraded_mode=degraded,
            )
        except Exception as exc:
            audit_log["error"] = str(exc)
            fallback_scores = {
                "aggregate_risk": _clamp(
                    sum(self._extract_numeric_signal(message) for message in agent_messages) / max(1, len(agent_messages))
                )
            }
            trusted_agent_output = {
                "weighted_scores": fallback_scores,
                "agent_trust_scores": {},
                "conflict_score": 1.0,
                "selected_agents": [],
                "deep_analysis_triggered": False,
                "reasoning_summary": "degraded_mode_exception",
            }
            return MetaDecisionResult(
                weighted_scores=fallback_scores,
                agent_trust_scores={},
                conflict_score=1.0,
                selected_agents=[],
                deep_analysis_triggered=False,
                reasoning_summary="degraded_mode_exception",
                trust_matrix={},
                deep_analysis_requests=[],
                trusted_agent_output=trusted_agent_output,
                audit_log=audit_log,
                reuse_context=None,
                degraded_mode=True,
            )
