from app.training.knowledge_curator import (
    AttackKnowledgeCurator,
    AttackKnowledgeSample,
    KnownAttackRecord,
)
from app.models import stable_hash


def test_curator_skips_already_known_attack() -> None:
    known = [
        KnownAttackRecord(
            record_id="known-1",
            title="Kerberoasting against weak AES-less service account",
            content_fingerprint=stable_hash(
                "Kerberoasting against weak AES-less service account "
                "Service account remains roastable and maps to privileged path. "
                "Kerberoasting against weak AES-less service account "
                "Service account remains roastable and maps to privileged path. "
                "T1558.003 kerberoast ad"
            ),
            technique_ids=["T1558.003"],
            tags=["kerberoast", "ad"],
        )
    ]
    curator = AttackKnowledgeCurator(known)
    sample = AttackKnowledgeSample(
        sample_id="s1",
        title="Kerberoasting against weak AES-less service account",
        summary="Service account remains roastable and maps to privileged path.",
        source="internal-red-team",
        content="Kerberoasting against weak AES-less service account Service account remains roastable and maps to privileged path.",
        technique_ids=["T1558.003"],
        tags=["kerberoast", "ad"],
        family="ad-credential-access",
    )

    decision = curator.evaluate(sample)

    assert decision.status == "skipped_known"
    assert decision.matched_records == ["known-1"]


def test_curator_rejects_unsafe_offensive_payload() -> None:
    curator = AttackKnowledgeCurator([])
    sample = AttackKnowledgeSample(
        sample_id="s2",
        title="Unsafe payload sample",
        summary="Raw beacon payload for review",
        source="unknown",
        content="msfvenom reverse_tcp powershell -enc raw launcher payload",
        technique_ids=["T1105"],
        tags=["payload"],
    )

    decision = curator.evaluate(sample)

    assert decision.status == "rejected"
    assert decision.reasons[0].startswith("unsafe_offensive_marker:")


def test_curator_assigns_novel_attack_to_relevant_agents() -> None:
    curator = AttackKnowledgeCurator([])
    sample = AttackKnowledgeSample(
        sample_id="s3",
        title="Ransomware propagation with AD privilege misuse",
        summary="Novel incident with containment decisions and AD privilege escalation indicators.",
        source="purple-team",
        content=(
            "Ransomware propagation showed lateral movement, containment pressure, "
            "privilege escalation, kerberos delegation abuse, and forensic needs."
        ),
        technique_ids=["T1486", "T1078", "T1558.003"],
        tags=["ransomware", "containment", "ad"],
        family="hybrid-impact",
    )

    plan = curator.build_plan([sample])

    assert plan.stats["accepted"] == 1
    assert "decision" in plan.agent_queues
    assert "remediation" in plan.agent_queues
    assert "ad" in plan.agent_queues
    assert "s3" in plan.agent_queues["decision"]
