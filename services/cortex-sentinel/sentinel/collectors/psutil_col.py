from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSUTIL_AVAILABLE = False
    psutil = None  # type: ignore[assignment]


SUSPICIOUS_PROCESSES = {
    "linux": {
        "nmap",
        "masscan",
        "hydra",
        "nc",
        "netcat",
        "tcpdump",
        "mimikatz",
        "john",
        "hashcat",
        "sqlmap",
        "msfconsole",
        "metasploit",
        "empire",
        "cobalt",
    },
    "windows": {"mimikatz.exe", "procdump.exe", "wce.exe", "pwdump.exe"},
}

SUSPICIOUS_COMMANDS = [
    "whoami /priv",
    "net user",
    "net localgroup administrators",
    "base64 -d",
    "bash -i",
    "/dev/tcp",
    "nc -e",
    "python -c import",
    "chmod +x /tmp",
    "curl http",
    "wget http",
    "eval(",
    "exec(",
]

INTERNAL_PREFIXES = (
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "192.168.",
    "127.",
)


@dataclass
class CollectedEvent:
    entity_id: str
    timestamp: float
    source: str
    event_type: str
    severity: float
    confidence: float
    process_name: str | None = None
    command: str | None = None
    target: str | None = None
    pid: int | None = None
    ppid: int | None = None
    user: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PsutilCollector:
    def collect_processes(self, entity_id: str) -> list[CollectedEvent]:
        if not PSUTIL_AVAILABLE:
            return []
        events: list[CollectedEvent] = []
        os_name = platform.system().lower()
        suspicious = SUSPICIOUS_PROCESSES.get(os_name, set())
        for proc in psutil.process_iter(["pid", "ppid", "name", "cmdline", "username"]):
            try:
                name = proc.info["name"] or ""
                cmd = " ".join(proc.info["cmdline"] or [])
                is_sus_name = name.lower() in suspicious
                is_sus_cmd = any(item in cmd.lower() for item in SUSPICIOUS_COMMANDS)
                if is_sus_name or is_sus_cmd:
                    events.append(
                        CollectedEvent(
                            entity_id=entity_id,
                            timestamp=time.time(),
                            source="psutil_process",
                            event_type="suspicious_process",
                            severity=0.85 if is_sus_name else 0.65,
                            confidence=0.70,
                            process_name=name,
                            command=cmd[:300],
                            pid=proc.info["pid"],
                            ppid=proc.info["ppid"],
                            user=proc.info["username"],
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return events

    def collect_connections(self, entity_id: str) -> list[CollectedEvent]:
        if not PSUTIL_AVAILABLE:
            return []
        events: list[CollectedEvent] = []
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "ESTABLISHED" and conn.raddr:
                    if any(conn.raddr.ip.startswith(prefix) for prefix in INTERNAL_PREFIXES):
                        events.append(
                            CollectedEvent(
                                entity_id=entity_id,
                                timestamp=time.time(),
                                source="psutil_process",
                                event_type="internal_connection",
                                severity=0.35,
                                confidence=0.65,
                                target=f"{conn.raddr.ip}:{conn.raddr.port}",
                                pid=conn.pid,
                            )
                        )
        except (psutil.AccessDenied, AttributeError):
            pass
        return events


class SentinelCollector:
    def __init__(self, entity_id: str):
        from .auditd import AuditdCollector
        from .falco import FalcoCollector

        self.entity_id = entity_id
        self._psutil = PsutilCollector()
        self._auditd = AuditdCollector()
        self._falco = FalcoCollector()

    def _in_k8s(self) -> bool:
        return os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")

    def collect(self) -> list[CollectedEvent]:
        events: list[CollectedEvent] = []
        if self._in_k8s() and self._falco.is_available():
            events.extend(self._falco.collect(self.entity_id))
        if platform.system() == "Linux":
            events.extend(self._auditd.collect(self.entity_id))
        events.extend(self._psutil.collect_processes(self.entity_id))
        events.extend(self._psutil.collect_connections(self.entity_id))
        return self._dedup(events)

    def _dedup(self, events: list[CollectedEvent]) -> list[CollectedEvent]:
        seen: set[tuple[str, int | None, int]] = set()
        unique: list[CollectedEvent] = []
        for event in events:
            key = (event.event_type, event.pid, int(event.timestamp))
            if key not in seen:
                seen.add(key)
                unique.append(event)
        return unique
