from app.learning_guard import LearningGuard
from app.models import LocalUpdate


def test_extreme_update_is_rejected() -> None:
    update = LocalUpdate(
        model_id="m1",
        machine_id="host-comp",
        tenant_id="tenant1",
        feature_schema_hash="abc",
        metrics={"quality": 1.0},
        delta={"x": 10.0, "y": 10.0, "z": 10.0},
        dataset_fingerprint="fp-1",
        signed_by="spiffe://cortex/sentinel/host-comp",
        suspicion_score=0.9,
        replay_nonce="nonce-xyz",
    )
    decision = LearningGuard().evaluate(update, True, True, False, 0.2)
    assert decision.quarantined is True
    assert "machine_compromised" in decision.reasons
    assert "roni_failed" in decision.reasons

