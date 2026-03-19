from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(payload: dict[str, Any] | list[Any] | str) -> str:
    if isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(slots=True)
class RawEvent:
    machine_id: str
    tenant_id: str
    source: str
    event_type: str
    event_time: datetime
    payload: dict[str, Any]
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(slots=True)
class NormalizedEvent:
    event_id: str
    machine_id: str
    tenant_id: str
    session_local_id: str
    event_type: str
    event_time: datetime
    process_lineage_summary: str
    feature_vector: dict[str, float]
    integrity_fields: dict[str, str | bool]
    confidence_local: float
    privacy_level: str
    trace_id: str
    redacted_payload: dict[str, Any]
    context: dict[str, Any]


@dataclass(slots=True)
class DriftStatus:
    soft_drift: bool
    hard_drift: bool
    adwin_mean: float
    page_hinkley_mean: float
    reasons: list[str]


@dataclass(slots=True)
class RiskScore:
    score: float
    severity: str
    confidence: float
    reasons: list[str]


@dataclass(slots=True)
class ModelSnapshot:
    model_id: str
    parent_model_id: str | None
    tenant_scope: str
    machine_scope: str
    class_scope: str
    training_window: str
    feature_schema_hash: str
    signed_manifest: dict[str, Any]
    evaluation_report: dict[str, Any]
    rollback_pointer: str | None
    parameters: dict[str, Any]


@dataclass(slots=True)
class LocalUpdate:
    model_id: str
    machine_id: str
    tenant_id: str
    feature_schema_hash: str
    metrics: dict[str, float]
    delta: dict[str, float]
    dataset_fingerprint: str
    signed_by: str
    suspicion_score: float
    replay_nonce: str


@dataclass(slots=True)
class LearningGuardDecision:
    accepted: bool
    quarantined: bool
    confidence_penalty: float
    reasons: list[str]


@dataclass(slots=True)
class PipelineOutcome:
    normalized_event: NormalizedEvent
    drift_status: DriftStatus
    risk: RiskScore
    update_decision: LearningGuardDecision
    emitted_records: list[dict[str, Any]]


@dataclass(slots=True)
class AuthenticatedPeer:
    spiffe_id: str
    certificate_fingerprint: str
    issued_at_epoch: int
    nonce: str
    tenant_id: str


@dataclass(slots=True)
class IngestDecision:
    accepted: bool
    reasons: list[str]
