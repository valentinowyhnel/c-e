from __future__ import annotations

import json
from typing import Any

from app.service import SentinelMachineService


class SentinelRuntime:
    def __init__(self, service: SentinelMachineService) -> None:
        self.service = service

    def register_command_subscription(self) -> bool:
        if self.service.nats_bus is None:
            return False

        async def on_command(msg: Any) -> None:
            command = json.loads(msg.data.decode("utf-8"))
            machine_id = command.get("machine_id")
            if machine_id not in {self.service.settings.machine_id, "*", None}:
                if hasattr(msg, "ack"):
                    await msg.ack()
                return
            await self.handle_command_async(command)
            if hasattr(msg, "ack"):
                await msg.ack()

        durable = f"sentinel-machine-{self.service.settings.machine_id}"
        return self.service.nats_bus.subscribe("cortex.sentinel.commands", on_command, durable)

    def handle_command(self, command: dict[str, object]) -> dict[str, object]:
        command_type = str(command.get("type", ""))
        if command_type == "flush_pending":
            flushed = self.service.transport.flush_pending()
            return {"accepted": True, "flushed": flushed}
        if command_type == "disable_nats_bus":
            if self.service.nats_bus is not None:
                self.service.nats_bus.stop()
                self.service.nats_bus = None
                self.service.transport.bus = None
            return {"accepted": True, "nats_bus": "disabled"}
        if command_type == "sync_shadow":
            if self.service.shadow is None:
                return {"accepted": False, "reason": "no_shadow_model"}
            response = self.service.control_plane.submit_model_candidate(self.service.shadow)
            return {"accepted": True, "response": response}
        return {"accepted": False, "reason": "unsupported_command"}

    async def handle_command_async(self, command: dict[str, object]) -> dict[str, object]:
        command_type = str(command.get("type", ""))
        if command_type == "flush_pending":
            flushed = await self.service.transport.flush_pending_async()
            return {"accepted": True, "flushed": flushed}
        return self.handle_command(command)
