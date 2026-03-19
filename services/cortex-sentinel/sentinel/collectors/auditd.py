from __future__ import annotations

import subprocess
import time

from .psutil_col import CollectedEvent, SUSPICIOUS_COMMANDS


class AuditdCollector:
    AUDIT_RULES = [
        "-a always,exit -F arch=b64 -S execve -k exec_watch",
        "-a always,exit -F arch=b64 -S connect -k net_watch",
        "-w /etc/passwd -p wa -k passwd_change",
        "-w /etc/shadow -p wa -k shadow_change",
        "-w /root/.ssh -p wa -k ssh_watch",
        "-w /etc/sudoers -p wa -k sudoers_watch",
    ]

    def setup(self) -> None:
        import os

        for rule in self.AUDIT_RULES:
            os.system(f"auditctl {rule} 2>/dev/null || true")

    def collect(self, entity_id: str, since_seconds: int = 10) -> list[CollectedEvent]:
        events: list[CollectedEvent] = []
        since = time.strftime("%m/%d/%Y %H:%M:%S", time.localtime(time.time() - since_seconds))
        try:
            result = subprocess.run(
                ["ausearch", "--start", since, "-i", "--format", "csv"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            for line in result.stdout.splitlines():
                event = self._parse(line, entity_id)
                if event is not None:
                    events.append(event)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return events

    def _parse(self, line: str, entity_id: str) -> CollectedEvent | None:
        try:
            parts = line.split(",")
            if len(parts) < 3:
                return None
            command = parts[2] if len(parts) > 2 else None
            severity = 0.5
            if command and any(item in command.lower() for item in SUSPICIOUS_COMMANDS):
                severity = 0.8
            event_type = "exec" if "execve" in line else "network_connect"
            return CollectedEvent(
                entity_id=entity_id,
                timestamp=time.time(),
                source="auditd_exec" if event_type == "exec" else "auditd_connect",
                event_type=event_type,
                severity=severity,
                confidence=0.85,
                command=command,
            )
        except Exception:
            return None
