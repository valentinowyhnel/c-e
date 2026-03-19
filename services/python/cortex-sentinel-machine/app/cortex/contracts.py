from __future__ import annotations

from dataclasses import asdict

from app.models import ModelSnapshot, PipelineOutcome


def build_ingest_payload(outcome: PipelineOutcome) -> dict[str, object]:
    event = outcome.normalized_event
    return {
        "event_id": event.event_id,
        "machine_id": event.machine_id,
        "tenant_id": event.tenant_id,
        "session_local_id": event.session_local_id,
        "event_type": event.event_type,
        "event_time": event.event_time.isoformat(),
        "trace_id": event.trace_id,
        "privacy_level": event.privacy_level,
        "process_lineage_summary": event.process_lineage_summary,
        "feature_vector": event.feature_vector,
        "integrity_fields": event.integrity_fields,
        "confidence_local": event.confidence_local,
    }


def build_trust_payload(outcome: PipelineOutcome) -> dict[str, object]:
    event = outcome.normalized_event
    risk = outcome.risk
    return {
        "entity_id": event.machine_id,
        "entity_type": "machine",
        "criticality": "normal",
        "environment": "preprod",
        "evidences": [
            {
                "signal_type": event.event_type,
                "source": "sentinel-machine",
                "severity": risk.score,
                "confidence": risk.confidence,
                "ttl_seconds": 300,
            }
        ],
        "resource_context": "normal",
    }


def build_model_candidate_payload(snapshot: ModelSnapshot) -> dict[str, object]:
    return {
        "model_id": snapshot.model_id,
        "parent_model_id": snapshot.parent_model_id,
        "tenant_scope": snapshot.tenant_scope,
        "machine_scope": snapshot.machine_scope,
        "class_scope": snapshot.class_scope,
        "training_window": snapshot.training_window,
        "feature_schema_hash": snapshot.feature_schema_hash,
        "signed_manifest": snapshot.signed_manifest,
        "evaluation_report": snapshot.evaluation_report,
        "rollback_pointer": snapshot.rollback_pointer,
        "parameters": snapshot.parameters,
    }

