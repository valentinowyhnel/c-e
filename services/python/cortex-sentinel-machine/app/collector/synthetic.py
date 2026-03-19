from __future__ import annotations

from datetime import timedelta

from app.config import RuntimeSettings
from app.models import RawEvent, utc_now


class SyntheticCollector:
    """Deterministic collector used for tests and offline validation."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self._cursor = 0

    def collect(self) -> list[RawEvent]:
        now = utc_now() + timedelta(seconds=self._cursor)
        self._cursor += 1
        payload = {
            "process": {"name": "powershell.exe", "pid": 4242, "ppid": 100, "cmdline": "powershell.exe -nop -enc AAAA"},
            "network": {"dst_ip": "198.51.100.10", "dst_port": 443, "dns_query": "rare.example"},
            "auth": {"user": "svc-admin", "elevated": True},
            "posture": {"patch_level": 0.91, "disk_encrypted": True, "tamper_flags": 0},
            "file": {"path": "C:/Windows/System32/tasks/backup", "sensitive": True},
        }
        return [
            RawEvent(
                machine_id=self.settings.machine_id,
                tenant_id=self.settings.tenant_id,
                source="synthetic",
                event_type="process_network_auth_combo",
                event_time=now,
                payload=payload,
            )
        ]
