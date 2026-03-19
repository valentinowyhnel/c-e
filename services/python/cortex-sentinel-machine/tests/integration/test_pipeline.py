from pathlib import Path
import shutil
import uuid

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.service import SentinelMachineService


def test_pipeline_offline_end_to_end() -> None:
    root = Path("test-artifacts") / f"integration-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    settings = RuntimeSettings(
        queue_path=root / "queue.log",
        state_dir=root / "state",
        min_training_support=1,
        promotion_patience=1,
    )
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    try:
        outcomes = service.process_once()
        assert len(outcomes) == 1
        assert service.queue.depth() >= 2
        assert outcomes[0].risk.severity in {"suspicious", "high-risk", "critical", "info"}
        assert (root / "state" / "audit.log").exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
