from pathlib import Path
from urllib.request import Request, urlopen
import shutil
import time
import uuid

from app.collector import SyntheticCollector
from app.config import RuntimeSettings
from app.observability import SecureObservabilityServer
from app.service import SentinelMachineService


def test_observability_endpoints_require_token() -> None:
    root = Path("test-artifacts") / f"obs-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    settings = RuntimeSettings(queue_path=root / "queue.log", state_dir=root / "state", observability_token="obs-token")
    service = SentinelMachineService(settings, SyntheticCollector(settings))
    service.process_once()
    server = SecureObservabilityServer(service, settings.observability_token)
    server.start("127.0.0.1", 18081)
    try:
        time.sleep(0.2)
        request = Request("http://127.0.0.1:18081/health", headers={"Authorization": "Bearer obs-token"})
        payload = urlopen(request, timeout=2).read().decode("utf-8")
        assert "queue_depth" in payload
    finally:
        server.stop()
        shutil.rmtree(root, ignore_errors=True)

