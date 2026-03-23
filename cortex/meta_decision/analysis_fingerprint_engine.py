from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def _normalize(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


@dataclass
class FingerprintResult:
    fingerprint: str
    version: str
    material: str

    def to_dict(self) -> dict[str, str]:
        return {
            "fingerprint": self.fingerprint,
            "version": self.version,
            "material": self.material,
        }


class AnalysisFingerprintEngine:
    def __init__(self, *, version: str = "v1") -> None:
        self.version = version

    def generate(
        self,
        *,
        event: dict[str, object],
        features: dict[str, object] | None = None,
        graph_context: dict[str, object] | None = None,
        trust_context: dict[str, object] | None = None,
    ) -> FingerprintResult:
        payload = {
            "event": _normalize(
                {
                    "scenario": event.get("scenario"),
                    "phase": event.get("phase"),
                    "source": event.get("source"),
                    "target": event.get("target"),
                    "asset_criticality": event.get("asset_criticality", 0.0),
                    "blast_radius": event.get("blast_radius", 0.0),
                    "novelty_score": event.get("novelty_score", 0.0),
                    "metadata": event.get("metadata", {}),
                }
            ),
            "features": _normalize(features or {}),
            "graph_context": _normalize(graph_context or {}),
            "trust_context": _normalize(trust_context or {}),
            "version": self.version,
        }
        material = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        fingerprint = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return FingerprintResult(fingerprint=fingerprint, version=self.version, material=material)
