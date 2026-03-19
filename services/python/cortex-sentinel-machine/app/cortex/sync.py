from __future__ import annotations

from app.cortex.client import CortexControlPlaneClient
from app.models import PipelineOutcome
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.service import SentinelMachineService


class CortexSyncCoordinator:
    def __init__(self, client: CortexControlPlaneClient) -> None:
        self.client = client

    def sync_outcome(self, service: SentinelMachineService, outcome: PipelineOutcome) -> dict[str, object]:
        ingest = self.client.push_event(outcome)
        trust = self.client.evaluate_trust(outcome)
        model = {}
        if service.shadow is not None:
            model = self.client.submit_model_candidate(service.shadow)
        return {"ingest": ingest, "trust": trust, "model": model}
