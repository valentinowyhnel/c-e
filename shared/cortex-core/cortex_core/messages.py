from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class MessageEnvelope(BaseModel):
    schema_version: str = "v1"
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    causation_id: str | None = None
    issued_at: float = Field(default_factory=time.time)
    expires_at: float | None = None
    retry_count: int = 0
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex)


class AgentTask(MessageEnvelope):
    task_id: str
    type: str
    entity_id: str | None = None
    entity_type: str | None = None
    execution_mode: str = "prepare"
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentTaskResult(MessageEnvelope):
    task_id: str
    agent_id: str
    success: bool
    output: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    requires_approval: bool = False
    approval_payload: dict[str, Any] | None = None
    actions_taken: list[dict[str, Any]] = Field(default_factory=list)
    execution_mode: str = "execute"
    capability_maturity: str = "beta"


class TrustUpdateEvent(MessageEnvelope):
    entity_id: str
    entity_type: str
    score_before: float
    score_after: float
    threat_level: str
    response_eligibility: str
    evidences: list[dict[str, Any]] = Field(default_factory=list)


class TrustDecisionEvent(MessageEnvelope):
    entity_id: str
    score_after: float
    threat_level: str
    response_eligibility: str


class ObservationEvent(MessageEnvelope):
    entity_id: str
    event_type: str
    source: str
    severity: float
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecurityEvent(MessageEnvelope):
    entity_id: str
    event_type: str
    severity: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)


class ADDriftEvent(MessageEnvelope):
    drift_id: str
    drift_type: str
    object_dn: str
    description: str
    severity: int
    auto_fixable: bool = False
    fix_action: str | None = None
