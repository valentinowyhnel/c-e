from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "phi3-mini"
    messages: list[Message] = Field(default_factory=list)
    max_tokens: int = 32
    temperature: float = 0.05
    stop: list[str] | None = None
    stream: bool = False


app = FastAPI(title="Cortex vLLM Local")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cortex-vllm"}


@app.get("/v1/models")
async def models() -> dict[str, list[dict[str, str]]]:
    return {
        "data": [
            {"id": "phi3-mini", "object": "model"},
            {"id": "mistral-7b", "object": "model"},
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest) -> dict[str, object]:
    content = _generate_content(req)
    return {
        "id": "chatcmpl-local",
        "object": "chat.completion",
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": sum(max(1, len(m.content) // 4) for m in req.messages),
            "completion_tokens": max(1, len(content) // 4),
            "total_tokens": sum(max(1, len(m.content) // 4) for m in req.messages) + max(1, len(content) // 4),
        },
    }


def _generate_content(req: ChatCompletionRequest) -> str:
    joined = "\n".join(message.content for message in req.messages).lower()

    if "reply with exactly one word" in joined:
        if "attack" in joined or "threat" in joined:
            return "classify_threat"
        if "rego" in joined or "policy" in joined:
            return "generate_rego"
        return "parse_log"

    if "classify the input into exactly one task type" in joined:
        if "rego" in joined or "policy" in joined or "admin access" in joined:
            return "generate_rego"
        if "attack" in joined or "threat" in joined or "anomaly" in joined:
            return "classify_threat"
        if "graph" in joined or "blast radius" in joined or "path" in joined:
            return "analyze_graph"
        if "parse" in joined or "log" in joined:
            return "parse_log"
        return "complex_reasoning"

    if req.model == "mistral-7b":
        return '{"classification":"security_event","severity":2,"confidence":0.88,"indicators":[],"suggested_action":"monitor"}'

    return "parse_log"
