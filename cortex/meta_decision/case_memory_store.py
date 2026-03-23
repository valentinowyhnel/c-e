from __future__ import annotations

import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


@dataclass
class MemoryCase:
    fingerprint: str
    fingerprint_version: str
    fingerprint_material: str
    scores: dict[str, float]
    agents_used: list[str]
    decision_finale: str
    validation: str
    model_version: str
    policy_version: str
    reusability_score: float
    created_at: float
    ttl_seconds: int
    invalidated: bool = False
    invalidation_reason: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        reference = time.time() if now is None else now
        return reference > self.created_at + self.ttl_seconds

    def similarity_to(self, material: str) -> float:
        return _clamp(SequenceMatcher(None, self.fingerprint_material, material).ratio())

    def to_dict(self) -> dict[str, object]:
        return {
            "fingerprint": self.fingerprint,
            "fingerprint_version": self.fingerprint_version,
            "scores": dict(self.scores),
            "agents_used": list(self.agents_used),
            "decision_finale": self.decision_finale,
            "validation": self.validation,
            "model_version": self.model_version,
            "policy_version": self.policy_version,
            "reusability_score": self.reusability_score,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "invalidated": self.invalidated,
            "invalidation_reason": self.invalidation_reason,
            "metadata": dict(self.metadata),
        }


class CaseMemoryStore:
    def __init__(self, *, default_ttl_seconds: int = 3600, max_items: int = 2000) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self.max_items = max_items
        self._cases: list[MemoryCase] = []

    def _active_cases(self, now: float | None = None) -> list[MemoryCase]:
        reference = time.time() if now is None else now
        active = [case for case in self._cases if not case.invalidated and not case.is_expired(reference)]
        self._cases = active[-self.max_items :]
        return list(self._cases)

    def store_case(
        self,
        *,
        fingerprint: str,
        fingerprint_version: str,
        fingerprint_material: str,
        scores: dict[str, float],
        agents_used: list[str],
        final_decision: str,
        validation: str,
        model_version: str,
        policy_version: str,
        reusability_score: float,
        ttl_seconds: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> MemoryCase:
        case = MemoryCase(
            fingerprint=fingerprint,
            fingerprint_version=fingerprint_version,
            fingerprint_material=fingerprint_material,
            scores=dict(scores),
            agents_used=list(agents_used),
            decision_finale=final_decision,
            validation=validation,
            model_version=model_version,
            policy_version=policy_version,
            reusability_score=_clamp(reusability_score),
            created_at=time.time(),
            ttl_seconds=ttl_seconds or self.default_ttl_seconds,
            metadata=dict(metadata or {}),
        )
        self._cases.append(case)
        self._cases = self._cases[-self.max_items :]
        return case

    def lookup(
        self,
        *,
        fingerprint: str,
        fingerprint_material: str,
        min_similarity: float = 0.74,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        matches: list[dict[str, object]] = []
        for case in self._active_cases():
            similarity = 1.0 if case.fingerprint == fingerprint else case.similarity_to(fingerprint_material)
            if similarity < min_similarity:
                continue
            matches.append({"case": case, "similarity": similarity})
        matches.sort(
            key=lambda item: (
                item["similarity"],
                item["case"].reusability_score,
                item["case"].created_at,
            ),
            reverse=True,
        )
        return matches[:limit]

    def invalidate(self, *, fingerprint: str, reason: str) -> int:
        count = 0
        for case in self._cases:
            if case.fingerprint != fingerprint:
                continue
            case.invalidated = True
            case.invalidation_reason = reason
            count += 1
        return count

    def snapshot(self) -> list[dict[str, object]]:
        return [case.to_dict() for case in self._active_cases()]
