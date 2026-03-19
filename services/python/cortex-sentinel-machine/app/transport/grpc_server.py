from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import json
import grpc

from app.models import AuthenticatedPeer, LocalUpdate, RawEvent
from app.transport.peer_identity import peer_from_grpc_context
from app.transport.tls import RotatingTLSState, TLSMaterialLoader

if TYPE_CHECKING:
    from app.config import RuntimeSettings
    from app.service import SentinelMachineService


def _json_deserializer(payload: bytes) -> dict[str, object]:
    if not payload:
        return {}
    return json.loads(payload.decode("utf-8"))


def _json_serializer(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True).encode("utf-8")


class SentinelGrpcAdapter:
    SERVICE_NAME = "cortex.sentinel.machine.v1.SentinelMachineIngest"

    def __init__(self, service: SentinelMachineService) -> None:
        self.service = service

    def method_handlers(self) -> grpc.GenericRpcHandler:
        handlers = {
            "PushEvent": grpc.unary_unary_rpc_method_handler(
                self.push_event,
                request_deserializer=_json_deserializer,
                response_serializer=_json_serializer,
            ),
            "UploadModelUpdate": grpc.unary_unary_rpc_method_handler(
                self.upload_model_update,
                request_deserializer=_json_deserializer,
                response_serializer=_json_serializer,
            ),
        }
        return grpc.method_handlers_generic_handler(self.SERVICE_NAME, handlers)

    def push_event(self, request: dict[str, object], context: grpc.ServicerContext) -> dict[str, object]:
        payload = dict(request)
        raw = RawEvent(
            machine_id=str(payload.get("machine_id", self.service.settings.machine_id)),
            tenant_id=str(payload.get("tenant_id", self.service.settings.tenant_id)),
            source="grpc",
            event_type=str(payload.get("event_type", "grpc_event")),
            event_time=datetime.fromisoformat(str(payload.get("event_time", datetime.now(timezone.utc).isoformat()))),
            payload=dict(payload.get("payload", {})),
            trace_id=str(payload.get("trace_id", "grpc-trace")),
        )
        outcome = self.service.process_raw_event(raw)
        return {
            "event_id": outcome.normalized_event.event_id,
            "local_score": outcome.risk.score,
            "severity": outcome.risk.severity,
            "confidence": outcome.risk.confidence,
            "soft_drift": outcome.drift_status.soft_drift,
            "hard_drift": outcome.drift_status.hard_drift,
        }

    def upload_model_update(self, request: dict[str, object], context: grpc.ServicerContext) -> dict[str, object]:
        metadata = dict(context.invocation_metadata())
        peer = peer_from_grpc_context(metadata, dict(context.auth_context()))
        update = LocalUpdate(
            model_id=str(request.get("model_id", "")),
            machine_id=str(request.get("machine_id", "")),
            tenant_id=str(request.get("tenant_id", "")),
            feature_schema_hash=str(request.get("feature_schema_hash", "")),
            metrics={str(key): float(value) for key, value in dict(request.get("metrics", {})).items()},
            delta={str(key): float(value) for key, value in dict(request.get("delta", {})).items()},
            dataset_fingerprint=str(request.get("dataset_fingerprint", "")),
            signed_by=str(request.get("signed_by", "")),
            suspicion_score=float(request.get("suspicion_score", 0.0)),
            replay_nonce=str(request.get("replay_nonce", "")),
        )
        decision = self.service.ingest_remote_update(peer, update)
        if not decision.accepted:
            context.set_code(grpc.StatusCode.PERMISSION_DENIED)
        return asdict(decision)


class SentinelGrpcServer:
    def __init__(self, service: SentinelMachineService, settings: RuntimeSettings) -> None:
        self.service = service
        self.settings = settings
        self.server = grpc.server(ThreadPoolExecutor(max_workers=4))
        self.adapter = SentinelGrpcAdapter(service)
        self.tls_state = RotatingTLSState(
            TLSMaterialLoader(settings.tls_server_cert_path, settings.tls_server_key_path, settings.tls_client_ca_path)
        )
        self.server.add_generic_rpc_handlers((self.adapter.method_handlers(),))

    def start(self, bind: str) -> int:
        if self.settings.grpc_tls_mode == "mtls":
            _, material = self.tls_state.refresh()
            credentials = grpc.ssl_server_credentials(
                [(material.server_key, material.server_cert)],
                root_certificates=material.client_ca,
                require_client_auth=True,
            )
            port = self.server.add_secure_port(bind, credentials)
        elif self.settings.grpc_tls_mode == "dev-insecure":
            port = self.server.add_insecure_port(bind)
        else:
            raise ValueError(f"unsupported grpc tls mode: {self.settings.grpc_tls_mode}")
        if port == 0:
            raise RuntimeError(f"failed to bind grpc server on {bind}")
        self.server.start()
        return port

    def stop(self, grace: float = 0) -> None:
        self.server.stop(grace)
