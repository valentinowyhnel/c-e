from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import time
import uuid

import grpc

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.service import SentinelMachineService
from app.transport import SentinelGrpcServer
from tests.support.certs import write_test_pki


def test_grpc_push_event_roundtrip() -> None:
    root = Path("test-artifacts") / f"grpc-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    settings = RuntimeSettings(queue_path=root / "queue.log", state_dir=root / "state", min_training_support=1)
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    server = SentinelGrpcServer(service, settings)
    port = server.start("localhost:0")
    try:
        time.sleep(0.2)
        channel = grpc.insecure_channel(f"localhost:{port}")
        stub = channel.unary_unary(
            "/cortex.sentinel.machine.v1.SentinelMachineIngest/PushEvent",
            request_serializer=lambda value: json.dumps(value).encode("utf-8"),
            response_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )
        response = stub(
            {
                "machine_id": settings.machine_id,
                "tenant_id": settings.tenant_id,
                "event_type": "grpc_event",
                "event_time": datetime.now(timezone.utc).isoformat(),
                "trace_id": "trace-1",
                "payload": {
                    "process": {"name": "cmd.exe", "pid": 1, "ppid": 0, "cmdline": "cmd.exe /c whoami"},
                    "network": {"dst_ip": "203.0.113.10", "dst_port": 22, "dns_query": "rare.example"},
                    "auth": {"user": "admin", "elevated": True},
                    "posture": {"patch_level": 0.7, "disk_encrypted": True, "tamper_flags": 0},
                    "file": {"path": "C:/tmp", "sensitive": False},
                },
            },
            timeout=3,
        )
        assert response["severity"] in {"info", "suspicious", "high-risk", "critical"}
    finally:
        server.stop(0)
        shutil.rmtree(root, ignore_errors=True)


def test_grpc_mtls_upload_model_update_roundtrip() -> None:
    root = Path("test-artifacts") / f"grpc-mtls-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    spiffe_id = "spiffe://cortex/sentinel-machine/host1"
    pki = write_test_pki(root / "pki", spiffe_id)
    settings = RuntimeSettings(
        queue_path=root / "queue.log",
        state_dir=root / "state",
        min_training_support=1,
        grpc_tls_mode="mtls",
        tls_server_cert_path=pki["server_cert"],
        tls_server_key_path=pki["server_key"],
        tls_client_ca_path=pki["ca_cert"],
    )
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    outcome = service.process_once()[0]
    expected_schema_hash = service._build_update(outcome.normalized_event, outcome.risk).feature_schema_hash
    server = SentinelGrpcServer(service, settings)
    port = server.start("localhost:0")
    try:
        time.sleep(0.2)
        creds = grpc.ssl_channel_credentials(
            root_certificates=pki["ca_cert"].read_bytes(),
            private_key=pki["client_key"].read_bytes(),
            certificate_chain=pki["client_cert"].read_bytes(),
        )
        channel = grpc.secure_channel(f"localhost:{port}", creds)
        stub = channel.unary_unary(
            "/cortex.sentinel.machine.v1.SentinelMachineIngest/UploadModelUpdate",
            request_serializer=lambda value: json.dumps(value).encode("utf-8"),
            response_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )
        response = stub(
            {
                "model_id": "shadow-1",
                "machine_id": settings.machine_id,
                "tenant_id": settings.tenant_id,
                "feature_schema_hash": expected_schema_hash,
                "metrics": {"quality": 0.9},
                "delta": {"a": 0.1},
                "dataset_fingerprint": "fp1",
                "signed_by": spiffe_id,
                "suspicion_score": 0.1,
                "replay_nonce": "replay-1",
            },
            metadata=(
                ("x-issued-at-epoch", str(int(time.time()))),
                ("x-peer-nonce", "peer-mtls-1"),
                ("x-tenant-id", settings.tenant_id),
            ),
            timeout=5,
        )
        assert response["accepted"] is True
    finally:
        server.stop(0)
        shutil.rmtree(root, ignore_errors=True)
