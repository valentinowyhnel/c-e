from time import time

from app.models import AuthenticatedPeer
from app.transport import SecureSessionGuard


def test_secure_session_guard_rejects_unauthorized_peer() -> None:
    guard = SecureSessionGuard("spiffe://cortex/sentinel-machine/")
    peer = AuthenticatedPeer(
        spiffe_id="spiffe://evil/agent/1",
        certificate_fingerprint="1234567890abcdef",
        issued_at_epoch=int(time()),
        nonce="n1",
        tenant_id="tenant1",
    )
    decision = guard.authorize_peer(peer, "tenant1")
    assert decision.accepted is False
    assert "unauthorized_spiffe" in decision.reasons


def test_secure_session_guard_rejects_replay() -> None:
    guard = SecureSessionGuard("spiffe://cortex/sentinel-machine/")
    peer = AuthenticatedPeer(
        spiffe_id="spiffe://cortex/sentinel-machine/host1",
        certificate_fingerprint="1234567890abcdef",
        issued_at_epoch=int(time()),
        nonce="n1",
        tenant_id="tenant1",
    )
    assert guard.authorize_peer(peer, "tenant1").accepted is True
    second = guard.authorize_peer(peer, "tenant1")
    assert second.accepted is False
    assert "peer_replay_detected" in second.reasons

