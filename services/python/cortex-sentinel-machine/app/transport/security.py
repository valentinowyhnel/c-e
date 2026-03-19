from __future__ import annotations

from time import time

from app.models import AuthenticatedPeer, IngestDecision


class SecureSessionGuard:
    def __init__(self, allowed_spiffe_prefix: str, max_clock_skew_seconds: int = 300) -> None:
        self.allowed_spiffe_prefix = allowed_spiffe_prefix
        self.max_clock_skew_seconds = max_clock_skew_seconds
        self._seen_nonces: set[str] = set()

    def authorize_peer(self, peer: AuthenticatedPeer, expected_tenant_id: str) -> IngestDecision:
        reasons: list[str] = []
        if not peer.spiffe_id.startswith(self.allowed_spiffe_prefix):
            reasons.append("unauthorized_spiffe")
        if peer.tenant_id != expected_tenant_id:
            reasons.append("tenant_scope_mismatch")
        if not peer.certificate_fingerprint:
            reasons.append("invalid_certificate_fingerprint")
        if abs(int(time()) - peer.issued_at_epoch) > self.max_clock_skew_seconds:
            reasons.append("peer_timestamp_outside_skew")
        if peer.nonce in self._seen_nonces:
            reasons.append("peer_replay_detected")
        self._seen_nonces.add(peer.nonce)
        return IngestDecision(accepted=not reasons, reasons=reasons)
