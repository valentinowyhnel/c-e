from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class BatchRequest:
    batch_id: str
    requests: list[dict[str, Any]]
    parallel: int = 4
    timeout_ms: int = 30_000


@dataclass(slots=True)
class BatchResult:
    batch_id: str
    results: list[dict[str, Any]]
    failed: list[dict[str, Any]]
    duration_ms: int


class BatchProcessor:
    MAX_PARALLEL = {"cpu_local": 4, "gpu_cloud": 8, "api": 5}

    def __init__(self, executor: Any, sentinel: Any):
        self.executor = executor
        self.sentinel = sentinel

    async def process(self, batch: BatchRequest, agent_id: str, agent_scopes: list[str]) -> BatchResult:
        started = time.monotonic()
        hardware = self._detect_batch_hardware(batch.requests)
        semaphore = asyncio.Semaphore(min(batch.parallel, self.MAX_PARALLEL.get(hardware, 4)))
        results: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        async def process_one(req: dict[str, Any], index: int) -> None:
            async with semaphore:
                verdict = await self.sentinel.check_tool_call(
                    agent_id=agent_id,
                    tool_name=req.get("tool", ""),
                    params=req.get("params", {}),
                    agent_scopes=agent_scopes,
                )
                if not verdict["allowed"]:
                    failed.append({"index": index, "error": f"sentinel_blocked: {verdict['reason']}"})
                    return

                try:
                    result = await asyncio.wait_for(
                        self.executor.execute_tool(req.get("tool", ""), req.get("params", {}), agent_id),
                        timeout=batch.timeout_ms / 1000,
                    )
                except asyncio.TimeoutError:
                    failed.append({"index": index, "error": "timeout"})
                    return
                results.append({"index": index, "result": result})

        checks = await asyncio.gather(
            *[
                self.sentinel.check_tool_call(
                    agent_id=agent_id,
                    tool_name=req.get("tool", ""),
                    params=req.get("params", {}),
                    agent_scopes=agent_scopes,
                )
                for req in batch.requests
            ]
        )
        if batch.requests and sum(1 for item in checks if not item["allowed"]) / len(batch.requests) > 0.3:
            return BatchResult(
                batch_id=batch.batch_id,
                results=[],
                failed=[{"error": "batch_cancelled_high_block_ratio"}],
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        await asyncio.gather(*[process_one(req, index) for index, req in enumerate(batch.requests)])
        return BatchResult(
            batch_id=batch.batch_id,
            results=sorted(results, key=lambda item: item["index"]),
            failed=failed,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def _detect_batch_hardware(self, requests: list[dict[str, Any]]) -> str:
        if any(req.get("tool") in {"generate_rego", "generate_script", "refactor_rego"} for req in requests):
            return "gpu_cloud"
        return "cpu_local"
