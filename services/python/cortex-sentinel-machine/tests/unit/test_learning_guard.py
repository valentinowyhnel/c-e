from app.learning_guard import LearningGuard
from app.models import LocalUpdate


def test_learning_guard_quarantines_replay() -> None:
    update = LocalUpdate(
        model_id="m1",
        machine_id="host1",
        tenant_id="tenant1",
        feature_schema_hash="abc",
        metrics={},
        delta={"x": 0.1},
        dataset_fingerprint="fp",
        signed_by="spiffe://cortex/agent/1",
        suspicion_score=0.1,
        replay_nonce="nonce-1",
    )
    guard = LearningGuard()
    first = guard.evaluate(update, False, False, True, 0.0)
    second = guard.evaluate(update, False, False, True, 0.0)
    assert first.accepted is True
    assert second.quarantined is True
    assert "replay_detected" in second.reasons

