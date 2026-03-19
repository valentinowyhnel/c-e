from pathlib import Path
import shutil
import uuid

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.service import SentinelMachineService


def test_health_stays_within_budget() -> None:
    root = Path("test-artifacts") / f"performance-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    settings = RuntimeSettings(queue_path=root / "queue.log", state_dir=root / "state")
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    try:
        for _ in range(5):
            service.process_once()
        health = service.health()
        assert health.cpu_overhead <= settings.cpu_budget_percent
        assert health.memory_overhead_mb <= settings.memory_budget_mb
    finally:
        shutil.rmtree(root, ignore_errors=True)
