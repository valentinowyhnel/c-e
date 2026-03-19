import asyncio
import json
import os
import time
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI, HTTPException, Request

try:
    import nats
except ImportError:  # pragma: no cover - optional in unit-test environments
    nats = None

try:
    import structlog
except ImportError:  # pragma: no cover - optional in unit-test environments
    import logging

    class _StructlogFallback:
        @staticmethod
        def get_logger():
            return logging.getLogger("cortex-obs-agent")

    structlog = _StructlogFallback()

from .anomaly import AnomalyEngine
from .models import AnomalyTestRequest

log = structlog.get_logger()

anomaly_engine = AnomalyEngine()
loop_status = {
    "telemetry": False,
    "correlation": False,
    "baseline": False,
    "health": False,
    "forecast": False,
    "sentinel_stream": False,
    "ad_drift_scan": False,
}
service_health: dict[str, dict[str, object]] = {}
nc_client: object | None = None
feed_events: list[dict[str, object]] = []
recent_sentinel_signals: list[dict[str, object]] = []
background_tasks: list[asyncio.Task[None]] = []


def service_auth_headers() -> dict[str, str]:
    token = os.getenv("CORTEX_INTERNAL_API_TOKEN", "").strip()
    return {"x-cortex-internal-token": token} if token else {}


def require_internal_api(request: Request) -> None:
    expected = os.getenv("CORTEX_INTERNAL_API_TOKEN", "").strip()
    if not expected:
        return
    if request.headers.get("x-cortex-internal-token", "") != expected:
        raise HTTPException(status_code=403, detail="internal_api_auth_required")


def record_event(event: dict[str, object]) -> None:
    feed_events.insert(0, event)
    del feed_events[200:]


async def publish(topic: str, payload: dict[str, object]) -> None:
    event = {
        "id": f"{topic}-{int(time.time() * 1000)}",
        "timestamp": payload.get("timestamp", time.time()),
        "type": topic.split(".")[-1] if topic.startswith("cortex.obs.") else "health",
        "severity": payload.get("severity", 1),
        "service": payload.get("service", "system"),
        "title": payload.get("title", topic),
        "explanation": payload.get("explanation", payload.get("reason", "")),
        "action_taken": payload.get("action_taken"),
        "requires_approval": payload.get("requires_approval", False),
        "approval_id": payload.get("approval_id"),
    }
    record_event(event)
    global nc_client
    if nc_client is None:
        return
    await nc_client.publish(topic, json.dumps(payload).encode())


async def telemetry_loop() -> None:
    loop_status["telemetry"] = True
    while True:
        await publish(
            "cortex.obs.actions",
            {
                "timestamp": time.time(),
                "service": "cortex-obs-agent",
                "title": "Telemetry loop active",
                "severity": 1,
                "action_taken": "monitor",
            },
        )
        await asyncio.sleep(30)


async def correlation_loop() -> None:
    loop_status["correlation"] = True
    while True:
        await asyncio.sleep(10)


async def baseline_loop() -> None:
    loop_status["baseline"] = True
    while True:
        await asyncio.sleep(300)


async def health_loop() -> None:
    loop_status["health"] = True
    urls = {
        "cortex-gateway": "http://cortex-gateway:8080/health",
        "cortex-mcp-server": "http://cortex-mcp-server:8080/health",
        "cortex-sentinel": "http://cortex-sentinel:8080/health",
        "cortex-victoriametrics": "http://cortex-victoriametrics:8428/health",
        "cortex-audit": "http://cortex-audit:8080/readyz",
        "cortex-approval": "http://cortex-approval:8080/readyz",
    }
    while True:
        now = int(time.time())
        async with httpx.AsyncClient(timeout=3.0) as client:
            for name, url in urls.items():
                try:
                    response = await client.get(url, headers=service_auth_headers())
                    service_health[name] = {
                        "status": "healthy" if response.status_code == 200 else "degraded",
                        "latency": response.elapsed.total_seconds() * 1000,
                        "trend": "stable",
                        "lastCheck": now,
                    }
                except Exception as exc:
                    service_health[name] = {
                        "status": "unreachable",
                        "latency": 0,
                        "trend": "degrading",
                        "lastCheck": now,
                        "error": str(exc),
                    }
        await publish(
            "cortex.obs.health",
            {"timestamp": time.time(), "services": service_health, "overall": "healthy"},
        )
        await asyncio.sleep(30)


async def forecast_loop() -> None:
    loop_status["forecast"] = True
    while True:
        await publish(
            "cortex.obs.forecasts",
            {
                "timestamp": time.time(),
                "service": "cortex-auth",
                "title": "No critical forecast",
                "severity": 1,
                "explanation": "Forecast loop active",
            },
        )
        await asyncio.sleep(60)


async def sentinel_stream_loop() -> None:
    global nc_client
    if nc_client is None:
        return
    loop_status["sentinel_stream"] = True
    js = nc_client.jetstream()

    async def on_sentinel(msg) -> None:
        try:
            data = json.loads(msg.data)
            recent_sentinel_signals.append(data)
            del recent_sentinel_signals[:-50]
            if len(recent_sentinel_signals) >= 3:
                classification = await anomaly_engine.classify_threshold(
                    value=float(len(recent_sentinel_signals)),
                    baseline=1.0,
                    metric="sentinel_correlation",
                )
                if classification.is_anomalous and classification.severity >= 3:
                    await publish(
                        "cortex.obs.anomalies",
                        {
                            "timestamp": time.time(),
                            "service": data.get("entity_id", "sentinel"),
                            "severity": classification.severity,
                            "title": "Sentinel correlation anomaly",
                            "explanation": f"entity={data.get('entity_id')} recent={len(recent_sentinel_signals)}",
                        },
                    )
                    await nc_client.publish(
                        "cortex.agents.tasks.decision",
                        json.dumps(
                            {
                                "task_id": f"decision-anomaly-{int(time.time())}",
                                "type": "analyze_response_decision",
                                "entity_id": data.get("entity_id"),
                                "entity_type": "machine",
                                "candidate_action": "monitor_or_quarantine",
                                "signals": recent_sentinel_signals[-10:],
                            }
                        ).encode(),
                    )
        finally:
            if hasattr(msg, "ack"):
                await msg.ack()

    async def on_sot(msg) -> None:
        try:
            data = json.loads(msg.data)
            entity_id = data.get("entity_id")
            await nc_client.publish(
                "cortex.agents.tasks.observer",
                json.dumps(
                    {
                        "task_id": f"sot-watch-{entity_id}-{int(time.time())}",
                        "type": "detect_deviation",
                        "agent_spiffe_id": f"spiffe://cortex.local/ns/cortex-system/sa/{entity_id}",
                        "priority": "high",
                    }
                ).encode(),
            )
        finally:
            if hasattr(msg, "ack"):
                await msg.ack()

    await js.subscribe("cortex.obs.stream", cb=on_sentinel, durable="obs-agent-sentinel-stream")
    await js.subscribe("cortex.obs.sot.issued", cb=on_sot, durable="obs-agent-sot-watcher")
    await asyncio.Event().wait()


async def ad_drift_scan_loop() -> None:
    global nc_client
    if nc_client is None:
        return
    loop_status["ad_drift_scan"] = True
    domain_dn = os.getenv("AD_DOMAIN_DN", "DC=corp,DC=local")
    while True:
        now = time.localtime()
        wait = ((26 - now.tm_hour) % 24) * 3600 - now.tm_min * 60
        if wait < 60:
            wait += 86400
        await asyncio.sleep(wait)
        await nc_client.publish(
            "cortex.agents.tasks.ad",
            json.dumps(
                {
                    "task_id": f"drift-scan-{int(time.time())}",
                    "type": "run_drift_scan",
                    "domain_dn": domain_dn,
                    "scheduled": True,
                }
            ).encode(),
        )
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global nc_client
    nats_url = os.getenv("NATS_URL", "nats://cortex-nats:4222")
    with suppress(Exception):
        if nats is not None:
            nc_client = await nats.connect(nats_url)

    background_tasks[:] = [
        asyncio.create_task(telemetry_loop()),
        asyncio.create_task(correlation_loop()),
        asyncio.create_task(baseline_loop()),
        asyncio.create_task(health_loop()),
        asyncio.create_task(forecast_loop()),
        asyncio.create_task(sentinel_stream_loop()),
        asyncio.create_task(ad_drift_scan_loop()),
    ]
    log.info("obs_agent.started")
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            with suppress(asyncio.CancelledError):
                await task
        background_tasks.clear()
        if nc_client is not None and hasattr(nc_client, "drain"):
            with suppress(Exception):
                await nc_client.drain()
        nc_client = None


app = FastAPI(title="Cortex Observability Agent", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {"status": "ok", "service": "cortex-obs-agent"}


@app.get("/status")
async def status(request: Request) -> dict[str, object]:
    require_internal_api(request)
    loops_active = sum(1 for active in loop_status.values() if active)
    return {"loops_active": loops_active, "health": service_health}


@app.get("/v1/feed")
async def feed(request: Request) -> list[dict[str, object]]:
    require_internal_api(request)
    return feed_events


@app.get("/v1/health")
async def health_map(request: Request) -> dict[str, dict[str, object]]:
    require_internal_api(request)
    return service_health


@app.post("/test/anomaly")
async def test_anomaly(request: Request) -> dict[str, object]:
    require_internal_api(request)
    payload = await request.json()
    anomaly_request = AnomalyTestRequest.model_validate(payload)
    classification = await anomaly_engine.classify_threshold(
        value=anomaly_request.value,
        baseline=anomaly_request.baseline,
        metric=anomaly_request.metric,
    )
    return {
        "service": anomaly_request.service,
        "is_anomalous": classification.is_anomalous,
        "anomaly_type": classification.anomaly_type,
        "severity": classification.severity,
        "confidence": classification.confidence,
    }
