from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class PriorityEvaluationRequest(BaseModel):
    entity_id: str
    anomaly_score: float = Field(ge=0.0, le=100.0)
    novelty_score: float = Field(ge=0.0, le=100.0)
    trust_score: float = Field(ge=0.0, le=100.0)
    graph_expansion: float = Field(ge=0.0, le=100.0, default=0.0)
    asset_criticality: float = Field(ge=0.0, le=100.0, default=0.0)
    campaign_likelihood: float = Field(ge=0.0, le=100.0, default=0.0)
    persistence_likelihood: float = Field(ge=0.0, le=100.0, default=0.0)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None


class PrioritySignal(BaseModel):
    signal: str = "priority_v2"
    entity_id: str
    priority_score: float = Field(ge=0.0, le=100.0)
    route: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    trace_id: str
    correlation_id: str | None = None


class PriorityEvaluationResponse(BaseModel):
    signal: PrioritySignal
    rationale: list[str] = Field(default_factory=list)
