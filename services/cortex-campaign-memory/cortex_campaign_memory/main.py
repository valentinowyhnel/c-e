from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from .models import CampaignEvaluationRequest, CampaignEvaluationResponse, CampaignEventFingerprint
from .store import CampaignMemoryStore


class AppState:
    def __init__(self) -> None:
        self.store = CampaignMemoryStore()
        self.started = False


def create_app() -> FastAPI:
    state = AppState()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.started = True
        yield

    app = FastAPI(
        title="Cortex Campaign Memory",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.campaign = state

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live", "service": "cortex-campaign-memory"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:
        return {"status": "ready", "service": "cortex-campaign-memory"}

    @app.get("/health/startup")
    async def health_startup(response: Response) -> dict[str, str]:
        if not state.started:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "started", "service": "cortex-campaign-memory"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body = "\n".join(
            [
                "# HELP cortex_campaign_memory_events_total Stored event fingerprints.",
                "# TYPE cortex_campaign_memory_events_total gauge",
                f"cortex_campaign_memory_events_total {len(state.store._events)}",
                "",
            ]
        )
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"service": "cortex-campaign-memory", "version": "0.1.0"}

    @app.post("/v1/campaign/events")
    async def store_event(event: CampaignEventFingerprint) -> dict[str, object]:
        state.store.store_event_fingerprint(event)
        return {"status": "stored", "event_id": event.event_id, "trace_id": event.trace_id}

    @app.post("/v1/campaign/evaluate", response_model=CampaignEvaluationResponse)
    async def evaluate(req: CampaignEvaluationRequest) -> CampaignEvaluationResponse:
        signal = state.store.campaign_likelihood_score(
            identity_id=req.identity_id,
            path_id=req.path_id,
            resource_family=req.resource_family,
            trace_id=req.trace_id,
            correlation_id=req.correlation_id,
        )
        return CampaignEvaluationResponse(
            signal=signal,
            rationale=[
                "Campaign memory aggregates weak signals over 24h, 7d, 30d and 90d.",
                "Likelihood remains advisory and is intended for Trust, Priority and Sentinel consumers.",
            ],
        )

    return app


app = create_app()
