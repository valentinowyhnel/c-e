from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from .engine import compute_priority
from .models import PriorityEvaluationRequest, PriorityEvaluationResponse


class AppState:
    def __init__(self) -> None:
        self.started = False
        self.requests = 0


def create_app() -> FastAPI:
    state = AppState()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        state.started = True
        yield

    app = FastAPI(
        title="Cortex Priority Engine",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.priority = state

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live", "service": "cortex-priority-engine"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:
        return {"status": "ready", "service": "cortex-priority-engine"}

    @app.get("/health/startup")
    async def health_startup(response: Response) -> dict[str, str]:
        if not state.started:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "started", "service": "cortex-priority-engine"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body = "\n".join(
            [
                "# HELP cortex_priority_engine_requests_total Number of priority evaluations.",
                "# TYPE cortex_priority_engine_requests_total counter",
                f"cortex_priority_engine_requests_total {state.requests}",
                "",
            ]
        )
        return Response(content=body, media_type="text/plain; version=0.0.4")

    @app.get("/version")
    async def version() -> dict[str, str]:
        return {"service": "cortex-priority-engine", "version": "0.1.0"}

    @app.post("/v1/priority/evaluate", response_model=PriorityEvaluationResponse)
    async def evaluate(req: PriorityEvaluationRequest) -> PriorityEvaluationResponse:
        state.requests += 1
        signal = compute_priority(req)
        return PriorityEvaluationResponse(
            signal=signal,
            rationale=[
                "Priority V2 remains a routing hint and not an enforcement decision.",
                "Trust and Policy still control critical actions.",
            ],
        )

    return app


app = create_app()
