from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]{1,}", re.IGNORECASE)
UNSAFE_MARKERS = (
    "meterpreter",
    "mimikatz sekurlsa",
    "cobalt strike",
    "msfvenom",
    "reverse_tcp",
    "powershell -enc",
)
STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "onto",
    "were",
    "been",
    "have",
    "your",
    "about",
    "after",
    "before",
    "than",
    "then",
}


def _normalize_text(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(_normalize_text(value))
        if len(token) > 2 and token not in STOP_WORDS
    }


def _fingerprint(value: str) -> str:
    return sha256(_normalize_text(value).encode("utf-8")).hexdigest()


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


@dataclass(slots=True)
class AttackKnowledgeSample:
    sample_id: str
    title: str
    summary: str
    source: str
    content: str
    technique_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    family: str = "unknown"
    severity: str = "medium"

    def combined_text(self) -> str:
        return " ".join(
            [
                self.title,
                self.summary,
                self.content,
                " ".join(self.technique_ids),
                " ".join(self.tags),
            ]
        )


@dataclass(slots=True)
class KnownAttackRecord:
    record_id: str
    title: str
    content_fingerprint: str
    technique_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CurationDecision:
    status: str
    accepted: bool
    novelty_score: float
    reasons: list[str]
    matched_records: list[str]
    assigned_agents: list[str]


@dataclass(slots=True)
class CuratedTrainingItem:
    sample_id: str
    title: str
    source: str
    family: str
    status: str
    novelty_score: float
    assigned_agents: list[str]
    reasons: list[str]
    matched_records: list[str]


@dataclass(slots=True)
class TrainingPlan:
    accepted: list[CuratedTrainingItem]
    skipped_known: list[CuratedTrainingItem]
    rejected: list[CuratedTrainingItem]
    agent_queues: dict[str, list[str]]
    stats: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "accepted": [asdict(item) for item in self.accepted],
            "skipped_known": [asdict(item) for item in self.skipped_known],
            "rejected": [asdict(item) for item in self.rejected],
            "agent_queues": self.agent_queues,
            "stats": self.stats,
        }


AGENT_PROFILES: dict[str, dict[str, set[str]]] = {
    "decision": {
        "tasks": {"decision_analysis", "high_risk_decision", "privilege_change_review"},
        "keywords": {"privilege", "approval", "containment", "critical", "identity", "tier0"},
    },
    "remediation": {
        "tasks": {"remediation_plan", "blast_radius_analysis", "apoptosis_explanation"},
        "keywords": {"containment", "lateral", "credential", "ransomware", "exfiltration"},
    },
    "ad": {
        "tasks": {"ad_drift_analysis", "privilege_path_analysis", "service_account_review"},
        "keywords": {"kerberoast", "dcsync", "delegation", "gpo", "domain", "ldap", "ad"},
    },
    "observer": {
        "tasks": {"event_correlation", "anomaly_detection", "telemetry_summarization"},
        "keywords": {"anomaly", "beacon", "telemetry", "burst", "network", "process"},
    },
    "soc": {
        "tasks": {"incident_investigation", "attack_path_analysis", "soc_question_answering"},
        "keywords": {"phishing", "exfiltration", "forensic", "lateral", "credential", "persistence"},
    },
}


class AttackKnowledgeCurator:
    """Defensive corpus curation with novelty gating and unsafe-content rejection."""

    def __init__(self, known_records: list[KnownAttackRecord] | None = None) -> None:
        self.known_records = known_records or []

    def build_plan(self, samples: list[AttackKnowledgeSample]) -> TrainingPlan:
        accepted: list[CuratedTrainingItem] = []
        skipped_known: list[CuratedTrainingItem] = []
        rejected: list[CuratedTrainingItem] = []
        agent_queues = {agent_id: [] for agent_id in AGENT_PROFILES}

        for sample in samples:
            decision = self.evaluate(sample)
            item = CuratedTrainingItem(
                sample_id=sample.sample_id,
                title=sample.title,
                source=sample.source,
                family=sample.family,
                status=decision.status,
                novelty_score=decision.novelty_score,
                assigned_agents=decision.assigned_agents,
                reasons=decision.reasons,
                matched_records=decision.matched_records,
            )
            if decision.status == "accepted":
                accepted.append(item)
                for agent_id in decision.assigned_agents:
                    agent_queues.setdefault(agent_id, []).append(sample.sample_id)
            elif decision.status == "skipped_known":
                skipped_known.append(item)
            else:
                rejected.append(item)

        return TrainingPlan(
            accepted=accepted,
            skipped_known=skipped_known,
            rejected=rejected,
            agent_queues=agent_queues,
            stats={
                "submitted": len(samples),
                "accepted": len(accepted),
                "skipped_known": len(skipped_known),
                "rejected": len(rejected),
            },
        )

    def evaluate(self, sample: AttackKnowledgeSample) -> CurationDecision:
        reasons: list[str] = []
        assigned_agents = self._assign_agents(sample)
        matched_records: list[str] = []
        combined_text = sample.combined_text()
        normalized = _normalize_text(combined_text)
        sample_fingerprint = _fingerprint(combined_text)
        sample_tokens = _tokens(combined_text)
        sample_techniques = {value.lower() for value in sample.technique_ids}

        if len(sample_tokens) < 8:
            return CurationDecision(
                status="rejected",
                accepted=False,
                novelty_score=0.0,
                reasons=["content_too_thin_for_defensive_training"],
                matched_records=[],
                assigned_agents=[],
            )

        for marker in UNSAFE_MARKERS:
            if marker in normalized:
                return CurationDecision(
                    status="rejected",
                    accepted=False,
                    novelty_score=0.0,
                    reasons=[f"unsafe_offensive_marker:{marker}"],
                    matched_records=[],
                    assigned_agents=[],
                )

        best_overlap = 0.0
        for record in self.known_records:
            matched = False
            if record.content_fingerprint == sample_fingerprint:
                matched = True
                best_overlap = 1.0
            else:
                record_tokens = _tokens(" ".join([record.title, " ".join(record.technique_ids), " ".join(record.tags)]))
                token_overlap = _jaccard(sample_tokens, record_tokens)
                technique_overlap = _jaccard(sample_techniques, {value.lower() for value in record.technique_ids})
                overlap = max(token_overlap, technique_overlap)
                best_overlap = max(best_overlap, overlap)
                matched = token_overlap >= 0.78 or technique_overlap >= 0.95
            if matched:
                matched_records.append(record.record_id)

        novelty_score = round(max(0.0, 1.0 - best_overlap), 3)

        if matched_records:
            reasons.append("already_covered_by_known_registry")
            return CurationDecision(
                status="skipped_known",
                accepted=False,
                novelty_score=novelty_score,
                reasons=reasons,
                matched_records=matched_records,
                assigned_agents=assigned_agents,
            )

        if not sample.technique_ids:
            reasons.append("no_attack_technique_tagged")
        if not assigned_agents:
            reasons.append("no_agent_profile_match")

        accepted = bool(sample.technique_ids and assigned_agents and novelty_score >= 0.2)
        if not accepted:
            return CurationDecision(
                status="rejected",
                accepted=False,
                novelty_score=novelty_score,
                reasons=reasons or ["novelty_below_threshold"],
                matched_records=[],
                assigned_agents=[],
            )

        reasons.extend(
            [
                f"novelty_score={novelty_score}",
                f"agents={','.join(assigned_agents)}",
            ]
        )
        return CurationDecision(
            status="accepted",
            accepted=True,
            novelty_score=novelty_score,
            reasons=reasons,
            matched_records=[],
            assigned_agents=assigned_agents,
        )

    def _assign_agents(self, sample: AttackKnowledgeSample) -> list[str]:
        text = sample.combined_text().lower()
        assigned: list[str] = []
        for agent_id, profile in AGENT_PROFILES.items():
            if any(keyword in text for keyword in profile["keywords"]):
                assigned.append(agent_id)
        return assigned


def load_samples(path: str) -> list[AttackKnowledgeSample]:
    payload = json.loads(open(path, "r", encoding="utf-8-sig").read())
    if not isinstance(payload, list):
        raise ValueError("samples file must contain a JSON array")
    return [AttackKnowledgeSample(**item) for item in payload]


def load_known_records(path: str | None) -> list[KnownAttackRecord]:
    if not path:
        return []
    payload = json.loads(open(path, "r", encoding="utf-8-sig").read())
    if not isinstance(payload, list):
        raise ValueError("known records file must contain a JSON array")
    return [KnownAttackRecord(**item) for item in payload]
