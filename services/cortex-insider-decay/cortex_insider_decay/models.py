from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class InsiderEvent(BaseModel):
    identity_id: str
    role: str
    expected_role: str
    justification_present: bool = True
    data_criticality: str = "normal"
    hour_utc: int = Field(default=12, ge=0, le=23)
    organization_context: str = "normal"
    legit_recovery: bool = False
    timestamp: float = Field(default_factory=time.time)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)


class InsiderEvaluationRequest(BaseModel):
    identity_id: str
    events: list[InsiderEvent]
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None


class InsiderDecaySignal(BaseModel):
    signal: str = "insider_trust_decay"
    identity_id: str
    role_misalignment_score: float = Field(ge=0.0, le=100.0)
    sensitive_access_without_context_score: float = Field(ge=0.0, le=100.0)
    cumulative_trust_decay: float = Field(ge=0.0, le=100.0)
    trust_decay_recovery: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    trace_id: str
    correlation_id: str | None = None


class InsiderDecayResponse(BaseModel):
    signal: InsiderDecaySignal
    rationale: list[str] = Field(default_factory=list)
