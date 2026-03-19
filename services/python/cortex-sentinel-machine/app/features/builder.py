from __future__ import annotations

from collections import Counter, deque
from math import log1p

from app.models import NormalizedEvent, stable_hash


class FeatureBuilder:
    def __init__(self, short_window: int = 32) -> None:
        self._recent_commands: deque[str] = deque(maxlen=short_window)
        self._recent_types: deque[str] = deque(maxlen=short_window)
        self._type_counts: Counter[str] = Counter()

    def build(self, event: NormalizedEvent) -> NormalizedEvent:
        payload = event.redacted_payload
        process = payload.get("process", {})
        network = payload.get("network", {})
        auth = payload.get("auth", {})
        posture = payload.get("posture", {})
        file_data = payload.get("file", {})

        command = str(process.get("cmdline", ""))
        command_hash = stable_hash(command)
        self._recent_commands.append(command_hash)
        self._recent_types.append(event.event_type)
        self._type_counts[event.event_type] += 1

        rarity = 1.0 / max(1, self._type_counts[event.event_type])
        burst = sum(1 for evt in self._recent_types if evt == event.event_type) / max(1, len(self._recent_types))

        event.feature_vector = {
            "cmd_hash_bucket": int(command_hash[:8], 16) % 997 / 997.0,
            "has_encoded_cmd": 1.0 if "[REDACTED]" in command or " -enc " in command.lower() else 0.0,
            "network_external": 1.0 if network.get("dst_ip") else 0.0,
            "network_sensitive_port": 1.0 if int(network.get("dst_port", 0)) in {22, 3389, 5985, 5986} else 0.0,
            "dns_rare": 1.0 if "rare" in str(network.get("dns_query", "")) else 0.0,
            "auth_elevated": 1.0 if auth.get("elevated") else 0.0,
            "file_sensitive": 1.0 if file_data.get("sensitive") else 0.0,
            "patch_gap": round(1.0 - float(posture.get("patch_level", 1.0)), 4),
            "disk_unencrypted": 0.0 if posture.get("disk_encrypted", False) else 1.0,
            "tamper_flags": float(posture.get("tamper_flags", 0)),
            "burst_score": round(burst, 4),
            "rarity_score": round(rarity, 4),
            "lineage_depth": float(str(event.process_lineage_summary).count("->")),
            "payload_size_log": round(log1p(len(str(payload))), 4),
        }
        event.context = {
            "maintenance_window": False,
            "machine_role": "default",
            "software_inventory_match": True,
            "recent_patch_event": posture.get("patch_level", 1.0) > 0.8,
        }
        return event

