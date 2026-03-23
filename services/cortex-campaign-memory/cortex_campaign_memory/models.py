from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class CampaignEventFingerprint(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_id: str
    path_id: str
    resource_family: str
    weak_signal_score: float = Field(default=0.0, ge=0.0, le=100.0)
    novelty_score: float = Field(default=0.0, ge=0.0, le=100.0)
    anomaly_score: float = Field(default=0.0, ge=0.0, le=100.0)
    timestamp: float = Field(default_factory=time.time)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignEvaluationRequest(BaseModel):
    identity_id: str
    path_id: str | None = None
    resource_family: str | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None


class AggregationWindow(BaseModel):
    window: str
    count: int
    weak_signal_sum: float
    novelty_avg: float
    anomaly_avg: float


class CampaignSignal(BaseModel):
    signal: str = "campaign_likelihood"
    identity_id: str
    path_id: str | None = None
    resource_family: str | None = None
    progressive_deviation_score: float = Field(ge=0.0, le=100.0)
    campaign_likelihood_score: float = Field(ge=0.0, le=100.0)
    windows: list[AggregationWindow] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    trace_id: str
    correlation_id: str | None = None
    inferred: bool = True


class CampaignEvaluationResponse(BaseModel):
    signal: CampaignSignal
    degraded: bool = False
    rationale: list[str] = Field(default_factory=list)
