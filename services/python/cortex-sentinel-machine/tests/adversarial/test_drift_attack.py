from app.drift import DriftDetectorSuite


def test_progressive_malicious_drift_triggers_soft_or_hard_drift() -> None:
    suite = DriftDetectorSuite()
    status = None
    for value in [0.1] * 10 + [0.95] * 40:
        status = suite.evaluate(score=value, feature_mean=value)
    assert status is not None
    assert status.soft_drift is True

