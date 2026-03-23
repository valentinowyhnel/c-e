from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class EdgeContext(BaseModel):
    ip_reputation: float = Field(default=0.0, ge=0.0, le=100.0)
    geo_consistency: float = Field(default=1.0, ge=0.0, le=1.0)
    device_fingerprint_present: bool = True
    path_anomaly_score: float = Field(default=0.0, ge=0.0, le=100.0)
    auth_context_score: float = Field(default=100.0, ge=0.0, le=100.0)
    previous_session_chain_score: float = Field(default=100.0, ge=0.0, le=100.0)
    transport_risk: float = Field(default=0.0, ge=0.0, le=100.0)
    vpn_or_proxy_detected: bool = False
    related_anomalous_sessions: int = Field(default=0, ge=0)
    asn_risk: float = Field(default=0.0, ge=0.0, le=100.0)
    asset_criticality: str = "normal"
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeInferenceRequest(BaseModel):
    session_id: str
    entity_id: str
    entity_type: str = "identity"
    machine_id: str | None = None
    tenant_id: str | None = None
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    auth_method: str = "password"
    scopes: list[str] = Field(default_factory=list)
    crown_jewels_exposed: bool = False
    blast_radius: int = Field(default=0, ge=0)
    context: EdgeContext


class EvidenceItem(BaseModel):
    code: str
    detail: str
    weight: float = Field(ge=0.0, le=1.0)


class EdgeRiskSignal(BaseModel):
    signal: str = "edge_risk_inferred"
    session_id: str
    entity_id: str
    entity_type: str
    inferred_edge_risk: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    inferred: bool = True
    trace_id: str
    correlation_id: str | None = None
    created_at: float = Field(default_factory=time.time)
    feature_flags: dict[str, bool] = Field(default_factory=dict)
    route_hint: str = "hybrid_analysis"


class EdgeInferenceResponse(BaseModel):
    signal: EdgeRiskSignal
    trust_response: dict[str, Any] | None = None
    degraded: bool = False
    rationale: list[str] = Field(default_factory=list)
