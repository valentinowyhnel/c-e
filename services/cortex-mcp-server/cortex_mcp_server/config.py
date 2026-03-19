from __future__ import annotations

import os
from dataclasses import dataclass


def _read_secret_file(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}

    values: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


@dataclass(slots=True)
class MCPServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    global_timeout_ms: int = 60_000
    routing_timeout_ms: int = 2_000
    sentinel_timeout_ms: int = 500
    rate_limit_per_minute: int = 60
    batch_max_size: int = 20
    batch_max_parallel: int = 8
    session_ttl_seconds: int = 1_800
    max_turns_per_session: int = 50
    max_input_size: int = 50_000
    max_output_size: int = 100_000
    prompt_injection_strict: bool = True
    pii_redaction_enabled: bool = True
    dry_run_default: bool = False
    phi3_endpoint: str = "http://vllm-cpu:8001"
    mistral_endpoint: str = "http://vllm-cpu:8002"
    llama3_endpoint: str = "http://vllm-gpu:8003"
    codellama_endpoint: str = "http://vllm-gpu:8004"
    sentinel_url: str = "http://cortex-sentinel:8080"
    trust_engine_url: str = "http://cortex-trust-engine:8080"
    internal_api_token: str = ""
    nats_url: str = "nats://cortex-nats:4222"
    agent_task_timeout_ms: int = 60_000
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_gpt5_model: str = "gpt-5"
    openai_gpt45_model: str = "gpt-4.5-preview"
    phi3_api_key: str = ""
    mistral_api_key: str = ""
    llama3_api_key: str = ""
    codellama_api_key: str = ""
    enforce_model_health: bool = False

    @classmethod
    def load(cls) -> "MCPServerConfig":
        secret_values = _read_secret_file("/vault/secrets/config")

        def get_str(name: str, default: str) -> str:
            return os.getenv(name, secret_values.get(name, default))

        def get_int(name: str, default: int) -> int:
            return int(get_str(name, str(default)))

        def get_bool(name: str, default: bool) -> bool:
            return get_str(name, str(default)).lower() in {"1", "true", "yes", "on"}

        return cls(
            host=get_str("HOST", "0.0.0.0"),
            port=get_int("PORT", 8080),
            global_timeout_ms=get_int("GLOBAL_TIMEOUT_MS", 60_000),
            routing_timeout_ms=get_int("ROUTING_TIMEOUT_MS", 2_000),
            sentinel_timeout_ms=get_int("SENTINEL_TIMEOUT_MS", 500),
            rate_limit_per_minute=get_int("RATE_LIMIT_PER_MINUTE", 60),
            batch_max_size=get_int("BATCH_MAX_SIZE", 20),
            batch_max_parallel=get_int("BATCH_MAX_PARALLEL", 8),
            session_ttl_seconds=get_int("SESSION_TTL_SECONDS", 1_800),
            max_turns_per_session=get_int("MAX_TURNS_PER_SESSION", 50),
            max_input_size=get_int("MAX_INPUT_SIZE", 50_000),
            max_output_size=get_int("MAX_OUTPUT_SIZE", 100_000),
            prompt_injection_strict=get_bool("PROMPT_INJECTION_STRICT", True),
            pii_redaction_enabled=get_bool("PII_REDACTION_ENABLED", True),
            dry_run_default=get_bool("DRY_RUN_DEFAULT", False),
            phi3_endpoint=get_str("PHI3_ENDPOINT", "http://vllm-cpu:8001"),
            mistral_endpoint=get_str("MISTRAL_ENDPOINT", "http://vllm-cpu:8002"),
            llama3_endpoint=get_str("LLAMA3_ENDPOINT", "http://vllm-gpu:8003"),
            codellama_endpoint=get_str("CODELLAMA_ENDPOINT", "http://vllm-gpu:8004"),
            sentinel_url=get_str("SENTINEL_URL", "http://cortex-sentinel:8080"),
            trust_engine_url=get_str("TRUST_ENGINE_URL", "http://cortex-trust-engine:8080"),
            internal_api_token=get_str("CORTEX_INTERNAL_API_TOKEN", ""),
            nats_url=get_str("NATS_URL", "nats://cortex-nats:4222"),
            agent_task_timeout_ms=get_int("AGENT_TASK_TIMEOUT_MS", 60_000),
            anthropic_api_key=get_str("ANTHROPIC_API_KEY", ""),
            claude_model=get_str("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            openai_api_key=get_str("OPENAI_API_KEY", ""),
            openai_base_url=get_str("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_gpt5_model=get_str("OPENAI_GPT5_MODEL", "gpt-5"),
            openai_gpt45_model=get_str("OPENAI_GPT45_MODEL", "gpt-4.5-preview"),
            phi3_api_key=get_str("PHI3_API_KEY", ""),
            mistral_api_key=get_str("MISTRAL_API_KEY", ""),
            llama3_api_key=get_str("LLAMA3_API_KEY", ""),
            codellama_api_key=get_str("CODELLAMA_API_KEY", ""),
            enforce_model_health=get_bool("ENFORCE_MODEL_HEALTH", False),
        )
