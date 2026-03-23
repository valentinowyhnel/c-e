from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class EdgeInferenceConfig:
    service_name: str = "cortex-edge-inference"
    version: str = "0.1.0"
    environment: str = "preprod"
    enabled: bool = True
    shadow_mode: bool = False
    trust_engine_url: str = "http://cortex-trust-engine:8080"
    audit_url: str = "http://cortex-audit:8080"
    internal_api_token: str = ""
    audit_required: bool = True
    trust_forward_enabled: bool = True
    trust_forward_required: bool = True
    request_timeout_seconds: float = 2.0
    max_evidence_count: int = 8

    @classmethod
    def load(cls) -> "EdgeInferenceConfig":
        return cls(
            environment=os.getenv("CORTEX_ENVIRONMENT", "preprod"),
            enabled=_env_bool("EDGE_INFERENCE_ENABLED", True),
            shadow_mode=_env_bool("EDGE_INFERENCE_SHADOW_MODE", False),
            trust_engine_url=os.getenv("TRUST_ENGINE_URL", "http://cortex-trust-engine:8080").rstrip("/"),
            audit_url=os.getenv("AUDIT_URL", "http://cortex-audit:8080").rstrip("/"),
            internal_api_token=os.getenv("CORTEX_INTERNAL_API_TOKEN", "").strip(),
            audit_required=_env_bool("EDGE_INFERENCE_AUDIT_REQUIRED", True),
            trust_forward_enabled=_env_bool("EDGE_INFERENCE_TRUST_FORWARD_ENABLED", True),
            trust_forward_required=_env_bool("EDGE_INFERENCE_TRUST_FORWARD_REQUIRED", True),
            request_timeout_seconds=float(os.getenv("EDGE_INFERENCE_TIMEOUT_SECONDS", "2.0")),
            max_evidence_count=int(os.getenv("EDGE_INFERENCE_MAX_EVIDENCE_COUNT", "8")),
        )
