from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CapabilityMaturity(str, Enum):
    PRODUCTION_READY = "production_ready"
    PREPROD_READY = "preprod_ready"
    BETA = "beta"
    EXPERIMENTAL = "experimental"
    STUBBED = "stubbed"


class DependencyState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ActionClass(str, Enum):
    READ_ONLY = "read_only"
    ADVISORY = "advisory"
    PREPARE_ONLY = "prepare_only"
    EXECUTE_WITH_APPROVAL = "execute_with_approval"
    IRREVERSIBLE = "irreversible"
    BLOCKED_IN_PROD = "blocked_in_prod"


class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"
    PREPARE = "prepare"
    EXECUTE = "execute"
    ROLLBACK = "rollback"


class ExecutionDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    PREPARE_ONLY = "prepare_only"
    BLOCKED_DUE_TO_DEGRADED_MODE = "blocked_due_to_degraded_mode"


class ResponseEligibility(str, Enum):
    NONE = "none"
    MONITOR_ONLY = "monitor_only"
    REVERSIBLE_ONLY = "reversible_only"
    APPROVAL_GATED = "approval_gated"
    AUTONOMOUS_ALLOWED = "autonomous_allowed"


class EvidenceSourceTrust(BaseModel):
    source: str
    trustworthiness: float = Field(ge=0.0, le=1.0, default=0.5)


class SecurityEvidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str
    source: str
    signal_type: str
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: float = Field(default_factory=time.time)
    ttl: int = Field(default=300, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyHealthSnapshot(BaseModel):
    nats: DependencyState = DependencyState.UNKNOWN
    neo4j: DependencyState = DependencyState.UNKNOWN
    bloodhound: DependencyState = DependencyState.UNKNOWN
    vault: DependencyState = DependencyState.UNKNOWN
    spire: DependencyState = DependencyState.UNKNOWN
    approval: DependencyState = DependencyState.UNKNOWN
    sentinel: DependencyState = DependencyState.UNKNOWN
    external_llm: DependencyState = DependencyState.UNKNOWN
    notes: list[str] = Field(default_factory=list)

    def critical_degraded(self) -> bool:
        return any(
            state == DependencyState.UNAVAILABLE
            for state in (self.nats, self.approval, self.sentinel)
        )


class ExecutionGuardrails(BaseModel):
    action_class: ActionClass
    reversible: bool = True
    approval_required: bool = False
    forensic_required: bool = False
    min_sources: int = 1
    min_trust_score: float = 0.0
    block_if_critical_dependencies_down: bool = True
    block_if_maturity_below: CapabilityMaturity = CapabilityMaturity.PREPROD_READY


class RiskEnvelope(BaseModel):
    entity_id: str
    entity_type: str
    action: str
    action_class: ActionClass
    trust_score: float = Field(ge=0.0, le=100.0)
    threat_level: int = Field(ge=0, le=5, default=0)
    evidence_count: int = Field(ge=0, default=0)
    strong_signal_count: int = Field(ge=0, default=0)
    distinct_sources: int = Field(ge=0, default=0)
    blast_radius: int = Field(ge=0, default=0)
    crown_jewels_exposed: bool = False
    criticality: str = "normal"
    scopes: list[str] = Field(default_factory=list)
    environment: str = "preprod"
    dry_run: bool = False
    maturity: CapabilityMaturity = CapabilityMaturity.BETA
    derived_signals: dict[str, Any] = Field(default_factory=dict)
    dependencies: DependencyHealthSnapshot = Field(default_factory=DependencyHealthSnapshot)
    evidences: list[SecurityEvidence] = Field(default_factory=list)


class SOTRecord(BaseModel):
    token_id: str = Field(default_factory=lambda: f"sot-{uuid.uuid4().hex[:12]}")
    entity_id: str
    entity_type: str
    reason_codes: list[str] = Field(default_factory=list)
    observation_level: str = "deep"
    restrictions: list[str] = Field(default_factory=list)
    issued_at: float = Field(default_factory=time.time)
    expires_at: float
    renewable: bool = False
    revoked_at: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
