from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(slots=True)
class RuntimeSettings:
    machine_id: str = field(default_factory=lambda: os.getenv("SENTINEL_MACHINE_ID", "machine-dev"))
    tenant_id: str = field(default_factory=lambda: os.getenv("SENTINEL_TENANT_ID", "tenant-dev"))
    machine_role: str = field(default_factory=lambda: os.getenv("SENTINEL_MACHINE_ROLE", "workstation"))
    queue_key: str = field(default_factory=lambda: os.getenv("SENTINEL_QUEUE_KEY", "sentinel-machine-dev-key-32-bytes!!"))
    queue_path: Path = field(default_factory=lambda: Path(os.getenv("SENTINEL_QUEUE_PATH", "./var/sentinel-queue.log")))
    state_dir: Path = field(default_factory=lambda: Path(os.getenv("SENTINEL_STATE_DIR", "./var/models")))
    policy_public_key_path: Path = field(default_factory=lambda: Path(os.getenv("SENTINEL_POLICY_PUBKEY", "./config/policy-public.pem")))
    model_signing_key_id: str = field(default_factory=lambda: os.getenv("SENTINEL_MODEL_SIGNING_KEY_ID", "spiffe://cortex/sentinel/dev"))
    cpu_budget_percent: float = field(default_factory=lambda: float(os.getenv("SENTINEL_CPU_BUDGET", "3.0")))
    memory_budget_mb: float = field(default_factory=lambda: float(os.getenv("SENTINEL_MEMORY_BUDGET_MB", "256")))
    max_queue_depth: int = field(default_factory=lambda: int(os.getenv("SENTINEL_MAX_QUEUE_DEPTH", "5000")))
    min_training_support: int = field(default_factory=lambda: int(os.getenv("SENTINEL_MIN_TRAINING_SUPPORT", "25")))
    promotion_patience: int = field(default_factory=lambda: int(os.getenv("SENTINEL_PROMOTION_PATIENCE", "3")))
    warmup_events: int = field(default_factory=lambda: int(os.getenv("SENTINEL_WARMUP_EVENTS", "50")))
    grpc_bind: str = field(default_factory=lambda: os.getenv("SENTINEL_GRPC_BIND", "127.0.0.1:50061"))
    observability_bind: str = field(default_factory=lambda: os.getenv("SENTINEL_OBSERVABILITY_BIND", "127.0.0.1:18080"))
    observability_token: str = field(default_factory=lambda: os.getenv("SENTINEL_OBSERVABILITY_TOKEN", "sentinel-observability-token"))
    grpc_tls_mode: str = field(default_factory=lambda: os.getenv("SENTINEL_GRPC_TLS_MODE", "dev-insecure"))
    tls_server_cert_path: Path = field(default_factory=lambda: Path(os.getenv("SENTINEL_TLS_SERVER_CERT", "./config/tls/server.crt")))
    tls_server_key_path: Path = field(default_factory=lambda: Path(os.getenv("SENTINEL_TLS_SERVER_KEY", "./config/tls/server.key")))
    tls_client_ca_path: Path = field(default_factory=lambda: Path(os.getenv("SENTINEL_TLS_CLIENT_CA", "./config/tls/ca.crt")))
    cortex_ingest_url: str = field(default_factory=lambda: os.getenv("SENTINEL_CORTEX_INGEST_URL", "http://127.0.0.1:28081"))
    cortex_trust_url: str = field(default_factory=lambda: os.getenv("SENTINEL_CORTEX_TRUST_URL", "http://127.0.0.1:28082"))
    cortex_model_url: str = field(default_factory=lambda: os.getenv("SENTINEL_CORTEX_MODEL_URL", "http://127.0.0.1:28083"))
    cortex_internal_token: str = field(default_factory=lambda: os.getenv("SENTINEL_CORTEX_INTERNAL_TOKEN", "cortex-internal-dev-token"))
    nats_url: str = field(default_factory=lambda: os.getenv("NATS_URL", "nats://cortex-nats:4222"))
    enable_nats_bus: bool = field(default_factory=lambda: os.getenv("SENTINEL_ENABLE_NATS_BUS", "0") == "1")
    nats_connect_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("SENTINEL_NATS_CONNECT_TIMEOUT", "0.2")))
