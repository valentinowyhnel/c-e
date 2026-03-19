from app.drift import DriftDetectorSuite
from app.models import NormalizedEvent, utc_now
from app.scoring import LocalScoringPipeline


def test_scoring_produces_severity() -> None:
    pipeline = LocalScoringPipeline(dimensions=3)
    drift = DriftDetectorSuite().evaluate(0.2, 0.2)
    event = NormalizedEvent(
        event_id="e1",
        machine_id="m1",
        tenant_id="t1",
        session_local_id="s1",
        event_type="proc",
        event_time=utc_now(),
        process_lineage_summary="1->2:test",
        feature_vector={"a": 0.8, "b": 1.0, "c": 0.9},
        integrity_fields={},
        confidence_local=0.0,
        privacy_level="redacted",
        trace_id="tr",
        redacted_payload={},
        context={},
    )
    risk = pipeline.score(event, drift)
    assert risk.severity in {"info", "suspicious", "high-risk", "critical"}
    assert 0.0 <= risk.score <= 1.0

