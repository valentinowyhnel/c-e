from __future__ import annotations

import json
import os
import subprocess
import time

from .psutil_col import CollectedEvent


class FalcoCollector:
    PRIORITY_SEVERITY = {
        "CRITICAL": 0.95,
        "HIGH": 0.80,
        "WARNING": 0.60,
        "NOTICE": 0.40,
        "INFO": 0.20,
    }

    HARD_STOP_RULES = {
        "Credential Dump Attempt",
        "Security Tool Killed",
        "Workload Identity Key Compromise",
    }

    def __init__(self, log_path: str = "/var/log/falco/events.json"):
        self.log_path = log_path

    def is_available(self) -> bool:
        return os.path.exists(self.log_path)

    def collect(self, entity_id: str, last_n: int = 20) -> list[CollectedEvent]:
        if not self.is_available():
            return []
        events: list[CollectedEvent] = []
        try:
            result = subprocess.run(
                ["tail", "-n", str(last_n), self.log_path],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    priority = data.get("priority", "INFO").upper()
                    rule = data.get("rule", "")
                    events.append(
                        CollectedEvent(
                            entity_id=entity_id,
                            timestamp=time.time(),
                            source="falco_rule",
                            event_type=rule or "falco_alert",
                            severity=self.PRIORITY_SEVERITY.get(priority, 0.5),
                            confidence=0.88,
                            metadata={
                                "rule": rule,
                                "output": data.get("output", "")[:200],
                                "priority": priority,
                                "hard_stop": rule in self.HARD_STOP_RULES,
                            },
                        )
                    )
                except Exception:
                    pass
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return events
