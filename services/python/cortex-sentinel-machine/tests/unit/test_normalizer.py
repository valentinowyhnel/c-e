from app.models import RawEvent, utc_now
from app.normalizer import EventNormalizer


def test_normalizer_redacts_sensitive_fields() -> None:
    event = RawEvent(
        machine_id="m1",
        tenant_id="t1",
        source="test",
        event_type="proc",
        event_time=utc_now(),
        payload={"process": {"cmdline": "powershell.exe -enc ABCD token=secret"}, "auth": {"user": "alice"}},
    )
    normalized = EventNormalizer().normalize(event)
    assert "[REDACTED]" in normalized.redacted_payload["process"]["cmdline"]
    assert normalized.redacted_payload["auth"]["user"] != "alice"

