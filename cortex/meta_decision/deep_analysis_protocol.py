from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeepAnalysisRequest:
    event_id: str
    agent_id: str
    reasons: list[str]
    deadline_ms: int
    expected_schema: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "reasons": list(self.reasons),
            "deadline_ms": self.deadline_ms,
            "expected_schema": dict(self.expected_schema),
        }


class DeepAnalysisProtocol:
    RESPONSE_SCHEMA = {
        "explanation": "string",
        "hypotheses": "list",
        "counterfactuals": "list",
        "feature_importance": "dict",
        "confidence_interval": "list",
    }

    def build_requests(
        self,
        *,
        event_id: str,
        agent_ids: list[str],
        reasons: list[str],
        deadline_ms: int = 150,
    ) -> list[DeepAnalysisRequest]:
        return [
            DeepAnalysisRequest(
                event_id=event_id,
                agent_id=agent_id,
                reasons=reasons,
                deadline_ms=deadline_ms,
                expected_schema=self.RESPONSE_SCHEMA,
            )
            for agent_id in agent_ids
        ]

    def standardize_response(self, response: dict[str, object]) -> dict[str, object]:
        return {
            "explanation": str(response.get("explanation", "")),
            "hypotheses": list(response.get("hypotheses", [])),
            "counterfactuals": list(response.get("counterfactuals", [])),
            "feature_importance": dict(response.get("feature_importance", {})),
            "confidence_interval": list(response.get("confidence_interval", [0.0, 0.0])),
        }
