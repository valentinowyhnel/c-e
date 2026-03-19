from __future__ import annotations

import time
from typing import Any

from .contracts import SOTRecord


def issue_sot(
    entity_id: str,
    entity_type: str,
    *,
    reason_codes: list[str],
    observation_level: str = "deep",
    restrictions: list[str] | None = None,
    ttl_seconds: int = 1800,
    renewable: bool = False,
    metadata: dict[str, Any] | None = None,
) -> SOTRecord:
    return SOTRecord(
        entity_id=entity_id,
        entity_type=entity_type,
        reason_codes=reason_codes,
        observation_level=observation_level,
        restrictions=restrictions or [],
        expires_at=time.time() + ttl_seconds,
        renewable=renewable,
        metadata=metadata or {},
    )


def expire_sot(record: SOTRecord) -> SOTRecord:
    record.expires_at = min(record.expires_at, time.time())
    return record


def revoke_sot(record: SOTRecord, reason: str) -> SOTRecord:
    record.revoked_at = time.time()
    record.metadata["revocation_reason"] = reason
    return record


def evaluate_sot_impact(record: SOTRecord) -> dict[str, Any]:
    now = time.time()
    active = record.revoked_at is None and record.expires_at > now
    trust_recovery_penalty = 0.5 if active and record.observation_level == "deep" else 0.25 if active else 0.0
    escalation_ready = active and len(record.reason_codes) >= 2
    return {
        "token_id": record.token_id,
        "active": active,
        "expired": record.expires_at <= now,
        "revoked": record.revoked_at is not None,
        "trust_recovery_penalty": trust_recovery_penalty,
        "escalation_ready": escalation_ready,
        "restriction_count": len(record.restrictions),
    }
