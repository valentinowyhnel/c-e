from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class AdminActionEvent(BaseModel):
    admin_id: str
    action: str
    resource_family: str
    privilege_level: str = "standard"
    timestamp: float = Field(default_factory=time.time)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminSessionRequest(BaseModel):
    admin_id: str
    actions: list[AdminActionEvent]
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None


class AdminCompromiseSignal(BaseModel):
    signal: str = "admin_compromise_suspected"
    admin_id: str
    admin_behavior_profile_score: float = Field(ge=0.0, le=100.0)
    action_chain_rarity: float = Field(ge=0.0, le=100.0)
    causal_break_score: float = Field(ge=0.0, le=100.0)
    admin_session_escalation_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    trace_id: str
    correlation_id: str | None = None


class AdminCompromiseResponse(BaseModel):
    signal: AdminCompromiseSignal
    rationale: list[str] = Field(default_factory=list)
