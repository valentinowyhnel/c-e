from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from cortex_core.contracts import (  # noqa: E402
    DependencyHealthSnapshot,
    ResponseEligibility,
    RiskEnvelope,
    SecurityEvidence,
)


class TrustDecision(str, Enum):
    ALLOW = "allow"
    MONITOR = "monitor"
    RESTRICTED = "restricted"
    DENY = "deny"
    REVOKE = "revoke"


class ThreatLevel(str, Enum):
    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class TrustEvaluationRequest(BaseModel):
    entity_id: str
    entity_type: str
    factors: list[str] = Field(default_factory=list)
    base_score: int = 50


class TrustEvaluationResponse(BaseModel):
    entity_id: str
    entity_type: str
    score: int
    decision: TrustDecision
    factors_applied: list[str]


class TrustEvaluateV2Request(BaseModel):
    entity_id: str
    entity_type: str = "machine"
    base_score: float = 85.0
    criticality: str = "normal"
    environment: str = "preprod"
    evidences: list[SecurityEvidence] = Field(default_factory=list)
    dependencies: DependencyHealthSnapshot = Field(default_factory=DependencyHealthSnapshot)


class TrustEvaluateV2Response(BaseModel):
    entity_id: str
    entity_type: str
    trust_score: float
    threat_level: ThreatLevel
    response_eligibility: ResponseEligibility
    decision: TrustDecision
    retained_evidence_count: int
    degraded: bool
    rationale: list[str]


class TrustProfile(BaseModel):
    entity_id: str
    entity_type: str
    score: float = 85.0
    threat_level: ThreatLevel = ThreatLevel.LOW
    response_eligibility: ResponseEligibility = ResponseEligibility.NONE
    updated_at: float = 0.0
