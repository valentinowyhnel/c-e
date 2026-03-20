from app.training.internal_sources import (
    ad_drifts_to_samples,
    audit_events_to_samples,
    bloodhound_paths_to_samples,
    build_internal_training_samples,
    soc_reports_to_samples,
)


def test_audit_events_to_samples_extracts_metadata() -> None:
    samples = audit_events_to_samples(
        [
            {
                "event_id": "evt-1",
                "event_type": "security.incident",
                "decision": "deny",
                "risk_level": 5,
                "reason": "Credential abuse tied to privilege path",
                "metadata": {
                    "technique_ids": ["T1558.003"],
                    "attack_path": True,
                    "ad_related": True,
                    "family": "credential-abuse",
                },
            }
        ]
    )

    assert len(samples) == 1
    assert samples[0].source == "cortex-audit"
    assert "T1558.003" in samples[0].technique_ids
    assert "ad" in samples[0].tags


def test_ad_drifts_to_samples_maps_drift_signal() -> None:
    samples = ad_drifts_to_samples(
        [
            {
                "drift_id": "drift-1",
                "drift_type": "sensitive_group_change",
                "description": "User added to Domain Admins outside workflow",
                "severity": 5,
            }
        ]
    )

    assert len(samples) == 1
    assert samples[0].family == "ad-drift"
    assert "T1558.003" in samples[0].technique_ids


def test_bloodhound_paths_to_samples_maps_privilege_paths() -> None:
    samples = bloodhound_paths_to_samples(
        [
            {
                "path_id": "path-1",
                "source": "svc-app",
                "target": "tier0",
                "path": ["svc-app", "Helpdesk", "Domain Admins", "tier0"],
            }
        ]
    )

    assert len(samples) == 1
    assert samples[0].source == "bloodhound-ce"
    assert "attack_path" in samples[0].tags


def test_soc_reports_to_samples_preserves_report_context() -> None:
    samples = soc_reports_to_samples(
        [
            {
                "report_id": "soc-1",
                "title": "Novel ransomware branching incident",
                "summary": "Observed ransomware staging and containment edge-cases.",
                "technique_ids": ["T1486"],
                "tags": ["ransomware", "containment"],
                "severity": "high",
            }
        ]
    )

    assert len(samples) == 1
    assert samples[0].source == "soc-report"
    assert "T1486" in samples[0].technique_ids


def test_build_internal_training_samples_returns_stats() -> None:
    samples, stats = build_internal_training_samples(
        audit_events=[{"event_id": "evt-1", "event_type": "incident", "metadata": {}}],
        ad_drifts=[{"drift_id": "drift-1", "drift_type": "gpo_drift", "description": "Changed GPO"}],
    )

    assert len(samples) == 2
    assert stats.as_dict()["audit_events"] == 1
    assert stats.as_dict()["ad_drifts"] == 1
