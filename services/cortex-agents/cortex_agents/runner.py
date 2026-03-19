from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import suppress
from pathlib import Path

from .agents import ADAgent, DecisionAgent, RemediationAgent

ROOT = Path(__file__).resolve().parents[3] / "shared" / "cortex-core"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.messages import AgentTask, AgentTaskResult  # noqa: E402


AGENTS = {
    "ad": ADAgent,
    "decision": DecisionAgent,
    "remediation": RemediationAgent,
}


async def main() -> None:
    agent_type = os.getenv("CORTEX_AGENT_TYPE", "ad")
    task_payload = os.getenv("CORTEX_AGENT_TASK")
    agent_cls = AGENTS.get(agent_type)
    if agent_cls is None:
        raise RuntimeError(f"unknown agent type: {agent_type}")
    agent = agent_cls()
    if task_payload:
        result = await agent.execute(json.loads(task_payload))
        print(json.dumps(result.output))
        return

    subject = {
        "ad": "cortex.agents.tasks.ad",
        "decision": "cortex.agents.tasks.decision",
        "remediation": "cortex.agents.tasks.remediation",
    }.get(agent_type)
    if not subject:
        await asyncio.Event().wait()
        return

    import nats

    nats_url = os.getenv("NATS_URL", "nats://cortex-nats:4222")
    nc = await nats.connect(nats_url)

    async def on_task(msg) -> None:
        raw_task = json.loads(msg.data)
        task_payload = {
            "task_id": raw_task["task_id"],
            "type": raw_task["type"],
            "entity_id": raw_task.get("entity_id"),
            "entity_type": raw_task.get("entity_type"),
            "execution_mode": raw_task.get("execution_mode", "prepare"),
            "payload": raw_task,
            "retry_count": raw_task.get("retry_count", 0),
        }
        for optional_key in ("correlation_id", "causation_id", "issued_at", "expires_at", "idempotency_key"):
            value = raw_task.get(optional_key)
            if value not in (None, ""):
                task_payload[optional_key] = value
        task_message = AgentTask.model_validate(task_payload)
        task = raw_task
        result = await agent.execute(task)
        result_message = AgentTaskResult(
            task_id=result.task_id,
            agent_id=result.agent_id,
            success=result.success,
            output=result.output,
            reasoning=result.reasoning,
            requires_approval=result.requires_approval,
            approval_payload=result.approval_payload,
            actions_taken=result.actions_taken,
            execution_mode=result.execution_mode,
            capability_maturity=result.capability_maturity,
            correlation_id=task_message.correlation_id,
            causation_id=task_message.task_id,
        )
        await nc.publish(
            f"{subject}.results",
            result_message.model_dump_json().encode(),
        )
        if hasattr(msg, "ack"):
            with suppress(Exception):
                await msg.ack()

    try:
        js = nc.jetstream()
        await js.subscribe(subject, cb=on_task, durable=f"{agent_type}-agent")
    except Exception:
        await nc.subscribe(subject, cb=on_task)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
