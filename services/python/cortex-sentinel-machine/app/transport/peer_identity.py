from __future__ import annotations

from app.models import AuthenticatedPeer


def peer_from_grpc_context(metadata: dict[str, str], auth_context: dict[str, list[bytes] | tuple[bytes, ...]]) -> AuthenticatedPeer:
    san_entries = auth_context.get("x509_subject_alternative_name", []) or []
    common_name_entries = auth_context.get("x509_common_name", []) or []
    fingerprint_entries = auth_context.get("transport_security_type", []) or []

    def _decode(values: list[bytes] | tuple[bytes, ...]) -> str:
        if not values:
            return ""
        first = values[0]
        return first.decode("utf-8", errors="ignore") if isinstance(first, bytes) else str(first)

    spiffe_id = _decode(san_entries)
    if not spiffe_id:
        spiffe_id = metadata.get("x-spiffe-id", "")

    fingerprint_hint = _decode(fingerprint_entries) or metadata.get("x-cert-fingerprint", "")
    return AuthenticatedPeer(
        spiffe_id=spiffe_id,
        certificate_fingerprint=fingerprint_hint,
        issued_at_epoch=int(metadata.get("x-issued-at-epoch", "0") or 0),
        nonce=metadata.get("x-peer-nonce", ""),
        tenant_id=metadata.get("x-tenant-id", ""),
    )
