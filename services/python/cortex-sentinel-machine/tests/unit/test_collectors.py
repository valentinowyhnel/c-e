from app.collector import CompositeCollector, SyntheticCollector
from app.config import RuntimeSettings


def test_synthetic_collector_returns_minimum_event() -> None:
    collector = SyntheticCollector(RuntimeSettings())
    events = collector.collect()
    assert len(events) == 1
    assert events[0].payload["process"]["name"]


def test_composite_collector_returns_at_least_one_event() -> None:
    collector = CompositeCollector(RuntimeSettings())
    events = collector.collect()
    assert len(events) >= 1
