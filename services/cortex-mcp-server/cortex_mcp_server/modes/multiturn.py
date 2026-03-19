from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..router import ModelID


@dataclass(slots=True)
class Turn:
    role: str
    content: str
    timestamp: float
    model_id: str
    tokens: int


@dataclass(slots=True)
class ConversationContext:
    session_id: str
    agent_id: str
    created_at: float
    last_active: float
    turns: list[Turn] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(turn.tokens for turn in self.turns)


class ContextWindowManager:
    MAX_TURNS_PER_MODEL = {
        ModelID.PHI3_MINI: 3,
        ModelID.MISTRAL_7B: 6,
        ModelID.LLAMA3_8B: 8,
        ModelID.CODELLAMA_13B: 12,
        ModelID.CLAUDE: 50,
    }

    def __init__(self, session_ttl_seconds: int = 1_800):
        self.session_ttl_seconds = session_ttl_seconds
        self._store: dict[str, ConversationContext] = {}

    async def load_context(self, session_id: str) -> ConversationContext | None:
        ctx = self._store.get(session_id)
        if ctx is None:
            return None
        if time.time() - ctx.last_active > self.session_ttl_seconds:
            self._store.pop(session_id, None)
            return None
        return ctx

    async def save_context(self, ctx: ConversationContext) -> None:
        ctx.last_active = time.time()
        self._store[ctx.session_id] = ctx

    def build_messages(
        self,
        ctx: ConversationContext,
        new_message: str,
        model_id: ModelID,
        system_prompt: str = "",
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        max_turns = self.MAX_TURNS_PER_MODEL[model_id]
        for turn in ctx.turns[-max_turns:]:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": new_message})
        return messages
