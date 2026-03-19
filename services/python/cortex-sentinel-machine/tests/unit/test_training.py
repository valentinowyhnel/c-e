from app.models import ModelSnapshot, NormalizedEvent, utc_now
from app.training import LocalTrainer


def test_shadow_training_preserves_rollback_pointer() -> None:
    trainer = LocalTrainer("tenant1", "machine1")
    event = NormalizedEvent(
        event_id="e1",
        machine_id="machine1",
        tenant_id="tenant1",
        session_local_id="s1",
        event_type="proc",
        event_time=utc_now(),
        process_lineage_summary="1->2:test",
        feature_vector={"a": 0.1, "b": 0.2},
        integrity_fields={},
        confidence_local=0.7,
        privacy_level="redacted",
        trace_id="tr1",
        redacted_payload={},
        context={},
    )
    trainer.observe(event)
    trainer.observe(event)
    parent = ModelSnapshot(
        model_id="champion-1",
        parent_model_id=None,
        tenant_scope="tenant1",
        machine_scope="machine1",
        class_scope="default",
        training_window="short=2,long=2",
        feature_schema_hash="schema-1",
        signed_manifest={},
        evaluation_report={},
        rollback_pointer=None,
        parameters={},
    )
    shadow = trainer.train_shadow(parent)
    assert shadow.parent_model_id == "champion-1"
    assert shadow.rollback_pointer == "champion-1"
