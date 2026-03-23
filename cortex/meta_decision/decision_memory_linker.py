from __future__ import annotations

from dataclasses import dataclass

from .analysis_fingerprint_engine import AnalysisFingerprintEngine, FingerprintResult
from .analysis_reuse_orchestrator import AnalysisReuseOrchestrator, ReuseDecision
from .case_memory_store import CaseMemoryStore


@dataclass
class MemoryAugmentedContext:
    fingerprint: str
    fingerprint_version: str
    fingerprint_material: str
    matching_cases: list[dict[str, object]]
    reuse: ReuseDecision

    def to_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "fingerprint_version": self.fingerprint_version,
            "fingerprint_material": self.fingerprint_material,
            "matching_cases": [
                {"similarity": item["similarity"], "case": item["case"].to_dict()}
                for item in self.matching_cases
            ],
            "reuse": self.reuse.to_dict(),
        }


class DecisionMemoryLinker:
    def __init__(
        self,
        *,
        fingerprint_engine: AnalysisFingerprintEngine,
        case_memory_store: CaseMemoryStore,
        reuse_orchestrator: AnalysisReuseOrchestrator,
    ) -> None:
        self.fingerprint_engine = fingerprint_engine
        self.case_memory_store = case_memory_store
        self.reuse_orchestrator = reuse_orchestrator

    def link(
        self,
        *,
        event: dict[str, object],
        features: dict[str, object] | None = None,
        graph_context: dict[str, object] | None = None,
        trust_context: dict[str, object] | None = None,
        novelty_score: float,
        criticality: float,
        policy_version: str,
        model_versions: dict[str, str],
        event_flags: dict[str, bool] | None = None,
    ) -> MemoryAugmentedContext:
        fingerprint_result: FingerprintResult = self.fingerprint_engine.generate(
            event=event,
            features=features,
            graph_context=graph_context,
            trust_context=trust_context,
        )
        matches = self.case_memory_store.lookup(
            fingerprint=fingerprint_result.fingerprint,
            fingerprint_material=fingerprint_result.material,
        )
        reuse = self.reuse_orchestrator.decide(
            fingerprint=fingerprint_result.fingerprint,
            matching_cases=matches,
            novelty_score=novelty_score,
            criticality=criticality,
            policy_version=policy_version,
            model_versions=model_versions,
            event_flags=event_flags,
        )
        return MemoryAugmentedContext(
            fingerprint=fingerprint_result.fingerprint,
            fingerprint_version=fingerprint_result.version,
            fingerprint_material=fingerprint_result.material,
            matching_cases=matches,
            reuse=reuse,
        )
