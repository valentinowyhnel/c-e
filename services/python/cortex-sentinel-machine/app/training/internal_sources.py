from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .knowledge_curator import AttackKnowledgeSample


@dataclass(slots=True)
class InternalCorpusStats:
    audit_events: int = 0
    ad_drifts: int = 0
    bloodhound_paths: int = 0
    soc_reports: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "audit_events": self.audit_events,
            "ad_drifts": self.ad_drifts,
            "bloodhound_paths": self.bloodhound_paths,
            "soc_reports": self.soc_reports,
        }


def _load_json_array(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in payload if isinstance(item, dict)]


def audit_events_to_samples(rows: list[dict[str, Any]]) -> list[AttackKnowledgeSample]:
    samples: list[AttackKnowledgeSample] = []
    for row in rows:
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        tags = ["audit", str(row.get("decision", "unknown"))]
        technique_ids = [value for value in metadata.get("technique_ids", []) if isinstance(value, str)]
        if metadata.get("attack_path"):
            tags.append("attack_path")
        if metadata.get("ad_related"):
            tags.append("ad")
        summary = str(row.get("reason", "") or metadata.get("summary", "")).strip()
        content = json.dumps(
            {
                "event_type": row.get("event_type", ""),
                "action": row.get("action", ""),
                "decision": row.get("decision", ""),
                "risk_level": row.get("risk_level", ""),
                "metadata": metadata,
            },
            sort_keys=True,
        )
        samples.append(
            AttackKnowledgeSample(
                sample_id=str(row.get("event_id", row.get("correlation_id", "")) or f"audit-{len(samples)+1}"),
                title=f"Audit incident: {row.get('event_type', 'security_event')}",
                summary=summary or "Audited Cortex incident for defensive review.",
                source="cortex-audit",
                content=content,
                technique_ids=technique_ids,
                tags=tags,
                family=str(metadata.get("family", "audit-incident")),
                severity=_risk_to_severity(row.get("risk_level")),
            )
        )
    return samples


def ad_drifts_to_samples(rows: list[dict[str, Any]]) -> list[AttackKnowledgeSample]:
    samples: list[AttackKnowledgeSample] = []
    for row in rows:
        drift_type = str(row.get("drift_type", "ad_drift"))
        description = str(row.get("description", "")).strip()
        fix_action = str(row.get("fix_action", "")).strip()
        technique_ids = _techniques_from_text(f"{drift_type} {description} {fix_action}")
        samples.append(
            AttackKnowledgeSample(
                sample_id=str(row.get("drift_id", f"drift-{len(samples)+1}")),
                title=f"AD drift: {drift_type}",
                summary=description or "Active Directory drift requiring review.",
                source="cortex.ad.drifts",
                content=json.dumps(row, sort_keys=True),
                technique_ids=technique_ids,
                tags=["ad", "drift", drift_type],
                family="ad-drift",
                severity=_risk_to_severity(row.get("severity")),
            )
        )
    return samples


def bloodhound_paths_to_samples(rows: list[dict[str, Any]]) -> list[AttackKnowledgeSample]:
    samples: list[AttackKnowledgeSample] = []
    for row in rows:
        source = str(row.get("source", row.get("from", ""))).strip()
        target = str(row.get("target", row.get("to", ""))).strip()
        path_nodes = row.get("path", row.get("nodes", []))
        if not isinstance(path_nodes, list):
            path_nodes = []
        flattened = " ".join(str(node) for node in path_nodes[:20])
        content = json.dumps(row, sort_keys=True)
        techniques = _techniques_from_text(f"{source} {target} {flattened}")
        samples.append(
            AttackKnowledgeSample(
                sample_id=str(row.get("path_id", f"path-{len(samples)+1}")),
                title=f"BloodHound path: {source or 'unknown'} -> {target or 'unknown'}",
                summary="Privilege path discovered in BloodHound graph.",
                source="bloodhound-ce",
                content=content,
                technique_ids=techniques,
                tags=["bloodhound", "attack_path", "privilege"],
                family="bloodhound-path",
                severity="high",
            )
        )
    return samples


def soc_reports_to_samples(rows: list[dict[str, Any]]) -> list[AttackKnowledgeSample]:
    samples: list[AttackKnowledgeSample] = []
    for row in rows:
        title = str(row.get("title", "SOC report")).strip()
        summary = str(row.get("summary", row.get("executive_summary", ""))).strip()
        content = json.dumps(row, sort_keys=True)
        techniques = [value for value in row.get("technique_ids", []) if isinstance(value, str)]
        if not techniques:
            techniques = _techniques_from_text(f"{title} {summary} {content}")
        tags = [value for value in row.get("tags", []) if isinstance(value, str)]
        tags.extend(["soc", "report"])
        samples.append(
            AttackKnowledgeSample(
                sample_id=str(row.get("report_id", f"soc-{len(samples)+1}")),
                title=title,
                summary=summary or "Normalized SOC report for defensive learning.",
                source="soc-report",
                content=content,
                technique_ids=techniques,
                tags=sorted(set(tags)),
                family=str(row.get("family", "soc-report")),
                severity=str(row.get("severity", "medium")),
            )
        )
    return samples


def build_internal_training_samples(
    *,
    audit_events: list[dict[str, Any]] | None = None,
    ad_drifts: list[dict[str, Any]] | None = None,
    bloodhound_paths: list[dict[str, Any]] | None = None,
    soc_reports: list[dict[str, Any]] | None = None,
) -> tuple[list[AttackKnowledgeSample], InternalCorpusStats]:
    audit_list = audit_events_to_samples(audit_events or [])
    drift_list = ad_drifts_to_samples(ad_drifts or [])
    path_list = bloodhound_paths_to_samples(bloodhound_paths or [])
    soc_list = soc_reports_to_samples(soc_reports or [])
    stats = InternalCorpusStats(
        audit_events=len(audit_list),
        ad_drifts=len(drift_list),
        bloodhound_paths=len(path_list),
        soc_reports=len(soc_list),
    )
    return audit_list + drift_list + path_list + soc_list, stats


def load_internal_corpus(
    *,
    audit_path: str | None = None,
    drift_path: str | None = None,
    bloodhound_path: str | None = None,
    soc_reports_path: str | None = None,
) -> tuple[list[AttackKnowledgeSample], InternalCorpusStats]:
    return build_internal_training_samples(
        audit_events=_load_json_array(audit_path),
        ad_drifts=_load_json_array(drift_path),
        bloodhound_paths=_load_json_array(bloodhound_path),
        soc_reports=_load_json_array(soc_reports_path),
    )


def _risk_to_severity(value: Any) -> str:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return "medium"
    if numeric >= 5:
        return "critical"
    if numeric >= 4:
        return "high"
    if numeric >= 2:
        return "medium"
    return "low"


def _techniques_from_text(value: str) -> list[str]:
    lowered = value.lower()
    techniques: list[str] = []
    if any(marker in lowered for marker in ("kerberoast", "delegation", "dcsync", "domain admin")):
        techniques.append("T1558.003")
    if any(marker in lowered for marker in ("gpo", "policy", "privilege path", "sensitive group")):
        techniques.append("T1484.001")
    if any(marker in lowered for marker in ("lateral", "attack path", "trust path", "tier0")):
        techniques.append("T1021")
    if any(marker in lowered for marker in ("ransomware", "encrypt", "containment", "exfiltration")):
        techniques.append("T1486")
    return sorted(set(techniques))
