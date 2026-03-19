from __future__ import annotations

from hashlib import sha256
import re

from app.models import NormalizedEvent, RawEvent, stable_hash


class EventNormalizer:
    SECRET_PATTERNS = [
        re.compile(r"(?i)(password|token|secret)=\S+"),
        re.compile(r"(?i)-enc\s+[A-Za-z0-9+/=]+"),
        re.compile(r"(?i)authorization:\s*bearer\s+\S+"),
    ]

    def normalize(self, event: RawEvent) -> NormalizedEvent:
        payload = self._redact(event.payload)
        process = payload.get("process", {})
        lineage = f"{process.get('ppid', 'na')}->{process.get('pid', 'na')}:{process.get('name', 'unknown')}"
        event_id = stable_hash(
            {
                "machine_id": event.machine_id,
                "trace_id": event.trace_id,
                "event_type": event.event_type,
                "event_time": event.event_time.isoformat(),
            }
        )
        integrity_fields = {
            "agent_binary_ok": payload.get("posture", {}).get("tamper_flags", 1) == 0,
            "payload_hash": stable_hash(payload),
            "schema_hash": stable_hash(sorted(payload.keys())),
        }
        return NormalizedEvent(
            event_id=event_id,
            machine_id=event.machine_id,
            tenant_id=event.tenant_id,
            session_local_id=sha256(f"{event.machine_id}:{event.event_time.date()}".encode("utf-8")).hexdigest()[:16],
            event_type=event.event_type,
            event_time=event.event_time,
            process_lineage_summary=lineage,
            feature_vector={},
            integrity_fields=integrity_fields,
            confidence_local=0.55,
            privacy_level="redacted",
            trace_id=event.trace_id,
            redacted_payload=payload,
            context={},
        )

    def _redact(self, payload: dict[str, object]) -> dict[str, object]:
        redacted: dict[str, object] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                redacted[key] = self._redact(value)
            elif isinstance(value, str):
                redacted[key] = self._redact_string(key, value)
            else:
                redacted[key] = value
        return redacted

    def _redact_string(self, key: str, value: str) -> str:
        if key in {"user", "path"}:
            return stable_hash(value)[:16]
        current = value
        for pattern in self.SECRET_PATTERNS:
            current = pattern.sub("[REDACTED]", current)
        return current

