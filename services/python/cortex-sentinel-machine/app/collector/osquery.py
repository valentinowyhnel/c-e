from __future__ import annotations

from datetime import timedelta
from subprocess import run
import platform

from app.config import RuntimeSettings
from app.models import RawEvent, utc_now


class OSCollector:
    """Best-effort local collector using native OS commands only."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def collect(self) -> list[RawEvent]:
        system = platform.system().lower()
        if system == "windows":
            return self._collect_windows()
        if system == "linux":
            return self._collect_linux()
        return []

    def _collect_windows(self) -> list[RawEvent]:
        now = utc_now()
        process_name = self._safe_run(["powershell", "-NoProfile", "-Command", "(Get-Process | Select-Object -First 1 -ExpandProperty ProcessName)"])
        net_line = self._safe_run(["powershell", "-NoProfile", "-Command", "(Get-NetTCPConnection | Select-Object -First 1 RemoteAddress,RemotePort | ConvertTo-Json -Compress)"])
        identity = self._safe_run(["whoami"])
        services = self._safe_run(["powershell", "-NoProfile", "-Command", "(Get-Service | Select-Object -First 3 Name,Status | ConvertTo-Json -Compress)"])
        tasks = self._safe_run(["powershell", "-NoProfile", "-Command", "(Get-ScheduledTask | Select-Object -First 3 TaskName,TaskPath | ConvertTo-Json -Compress)"])
        return [
            RawEvent(
                machine_id=self.settings.machine_id,
                tenant_id=self.settings.tenant_id,
                source="windows-native",
                event_type="windows_process_snapshot",
                event_time=now,
                payload={
                    "process": {"name": process_name or "unknown.exe", "pid": 0, "ppid": 0, "cmdline": "snapshot"},
                    "network": {"dst_ip": net_line, "dst_port": 0, "dns_query": ""},
                    "auth": {"user": identity or "unknown", "elevated": "admin" in (identity or "").lower()},
                    "posture": {"patch_level": 0.8, "disk_encrypted": True, "tamper_flags": 0},
                    "file": {"path": "C:/Windows/System32", "sensitive": False},
                },
            )
            ,
            RawEvent(
                machine_id=self.settings.machine_id,
                tenant_id=self.settings.tenant_id,
                source="windows-native",
                event_type="windows_persistence_snapshot",
                event_time=now,
                payload={
                    "process": {"name": "services.exe", "pid": 0, "ppid": 0, "cmdline": "snapshot"},
                    "network": {"dst_ip": "", "dst_port": 0, "dns_query": ""},
                    "auth": {"user": identity or "unknown", "elevated": "admin" in (identity or "").lower()},
                    "posture": {"patch_level": 0.8, "disk_encrypted": True, "tamper_flags": 0},
                    "file": {"path": tasks or services or "C:/Windows/Tasks", "sensitive": True},
                },
            )
        ]

    def _collect_linux(self) -> list[RawEvent]:
        now = utc_now() + timedelta(milliseconds=1)
        process_name = self._safe_run(["sh", "-lc", "ps -eo comm= | head -n 1"])
        net_line = self._safe_run(["sh", "-lc", "ss -tunp | head -n 2 | tail -n 1"])
        identity = self._safe_run(["whoami"])
        systemd = self._safe_run(["sh", "-lc", "systemctl list-units --type=service --no-pager | head -n 3"])
        cron = self._safe_run(["sh", "-lc", "crontab -l 2>/dev/null | head -n 3"])
        sudoers = self._safe_run(["sh", "-lc", "grep -v '^#' /etc/sudoers 2>/dev/null | head -n 1"])
        return [
            RawEvent(
                machine_id=self.settings.machine_id,
                tenant_id=self.settings.tenant_id,
                source="linux-native",
                event_type="linux_process_snapshot",
                event_time=now,
                payload={
                    "process": {"name": process_name or "unknown", "pid": 0, "ppid": 0, "cmdline": "snapshot"},
                    "network": {"dst_ip": net_line, "dst_port": 0, "dns_query": ""},
                    "auth": {"user": identity or "unknown", "elevated": identity == "root"},
                    "posture": {"patch_level": 0.8, "disk_encrypted": True, "tamper_flags": 0},
                    "file": {"path": "/etc", "sensitive": False},
                },
            )
            ,
            RawEvent(
                machine_id=self.settings.machine_id,
                tenant_id=self.settings.tenant_id,
                source="linux-native",
                event_type="linux_privilege_persistence_snapshot",
                event_time=now,
                payload={
                    "process": {"name": "systemd", "pid": 1, "ppid": 0, "cmdline": "snapshot"},
                    "network": {"dst_ip": "", "dst_port": 0, "dns_query": ""},
                    "auth": {"user": identity or "unknown", "elevated": identity == "root"},
                    "posture": {"patch_level": 0.8, "disk_encrypted": True, "tamper_flags": 0},
                    "file": {"path": cron or sudoers or systemd or "/etc/systemd", "sensitive": True},
                },
            )
        ]

    def _safe_run(self, command: list[str]) -> str:
        try:
            completed = run(command, capture_output=True, text=True, timeout=3, check=False)
            return completed.stdout.strip()[:256]
        except Exception:
            return ""
