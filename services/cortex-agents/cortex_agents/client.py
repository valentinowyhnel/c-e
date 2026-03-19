from __future__ import annotations

import httpx


class MCPClient:
    def __init__(self, agent_id: str, base_url: str = "http://cortex-mcp-server:8080"):
        self.agent_id = agent_id
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=60.0)

    async def __aenter__(self):
        if self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()

    async def call_tool(self, tool_name: str, params: dict):
        response = await self._client.post(
            "/mcp/tools/call",
            json={
                "tool": tool_name,
                "params": params,
                "agent_id": self.agent_id,
                "agent_scopes": ["admin:write"],
            },
        )
        response.raise_for_status()
        return response.json()

    async def complete(
        self,
        task: str,
        input_data: str,
        system_prompt: str = "",
        max_tokens: int = 600,
        temperature: float = 0.2,
        params: dict | None = None,
    ):
        response = await self._client.post(
            "/mcp/complete",
            json={
                "task": task,
                "input": input_data,
                "system_prompt": system_prompt,
                "params": {
                    **(params or {}),
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            },
        )
        response.raise_for_status()
        return response.json()
