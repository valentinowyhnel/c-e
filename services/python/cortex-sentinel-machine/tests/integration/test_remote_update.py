from time import time

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.models import AuthenticatedPeer, LocalUpdate
from app.service import SentinelMachineService


def test_remote_update_from_unauthorized_agent_is_refused() -> None:
    settings = RuntimeSettings(min_training_support=1)
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    service.process_once()
    peer = AuthenticatedPeer(
        spiffe_id="spiffe://evil/host1",
        certificate_fingerprint="1234567890abcdef",
        issued_at_epoch=int(time()),
        nonce="peer-1",
        tenant_id=settings.tenant_id,
    )
    update = LocalUpdate(
        model_id="shadow-1",
        machine_id=settings.machine_id,
        tenant_id=settings.tenant_id,
        feature_schema_hash="schema-x",
        metrics={"quality": 0.9},
        delta={"a": 0.1},
        dataset_fingerprint="fp1",
        signed_by="spiffe://evil/host1",
        suspicion_score=0.1,
        replay_nonce="model-1",
    )
    decision = service.ingest_remote_update(peer, update)
    assert decision.accepted is False
    assert "unauthorized_spiffe" in decision.reasons


def test_remote_update_with_schema_mismatch_is_refused() -> None:
    settings = RuntimeSettings(min_training_support=1)
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    service.process_once()
    peer = AuthenticatedPeer(
        spiffe_id="spiffe://cortex/sentinel-machine/host1",
        certificate_fingerprint="1234567890abcdef",
        issued_at_epoch=int(time()),
        nonce="peer-2",
        tenant_id=settings.tenant_id,
    )
    update = LocalUpdate(
        model_id="shadow-1",
        machine_id=settings.machine_id,
        tenant_id=settings.tenant_id,
        feature_schema_hash="bad-schema",
        metrics={"quality": 0.9},
        delta={"a": 0.1},
        dataset_fingerprint="fp1",
        signed_by="spiffe://cortex/sentinel-machine/host1",
        suspicion_score=0.1,
        replay_nonce="model-2",
    )
    decision = service.ingest_remote_update(peer, update)
    assert decision.accepted is False
    assert "feature_schema_mismatch" in decision.reasons

