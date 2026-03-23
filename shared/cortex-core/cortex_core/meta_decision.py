from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class AgentSignal(BaseModel):
    schema_version: str = "v1"
    event_type: str = "agent_signal"
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    entity_id: str
    entity_type: str = "unknown"
    agent_id: str
    specialty: str = "general"
    risk_signal: float = Field(ge=0.0, le=1.0)
    priority: float = Field(ge=0.0, le=1.0, default=0.5)
    runtime_trust: float = Field(ge=0.0, le=1.0, default=0.5)
    uncertainty: float = Field(ge=0.0, le=1.0, default=0.5)
    data_quality: float = Field(ge=0.0, le=1.0, default=0.5)
    reasoning_quality: float = Field(ge=0.0, le=1.0, default=0.5)
    requires_approval: bool = False
    success: bool = True
    explanation: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class DeepAnalysisRequest(BaseModel):
    event_id: str
    entity_id: str
    agent_id: str
    reasons: list[str] = Field(default_factory=list)
    deadline_ms: int = Field(default=150, ge=1)


class TrustedAgentOutput(BaseModel):
    weighted_scores: dict[str, float] = Field(default_factory=dict)
    agent_trust_scores: dict[str, float] = Field(default_factory=dict)
    conflict_score: float = Field(ge=0.0, le=1.0, default=0.0)
    selected_agents: list[str] = Field(default_factory=list)
    deep_analysis_triggered: bool = False
    reasoning_summary: str = ""


class MetaDecisionAssessmentRequest(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str
    entity_type: str = "unknown"
    novelty_score: float = Field(ge=0.0, le=1.0, default=0.0)
    graph_score: float = Field(ge=0.0, le=1.0, default=0.0)
    temporal_score: float = Field(ge=0.0, le=1.0, default=0.0)
    asset_criticality: float = Field(ge=0.0, le=1.0, default=0.0)
    blast_radius: float = Field(ge=0.0, le=1.0, default=0.0)
    crown_jewel: bool = False
    signals: list[AgentSignal] = Field(default_factory=list)


class MetaDecisionEvent(BaseModel):
    event_id: str
    entity_id: str
    entity_type: str
    trusted_output: TrustedAgentOutput
    deep_analysis_requests: list[DeepAnalysisRequest] = Field(default_factory=list)
    audit_log: dict[str, Any] = Field(default_factory=dict)
    degraded_mode: bool = False
    timestamp: float = Field(default_factory=time.time)
