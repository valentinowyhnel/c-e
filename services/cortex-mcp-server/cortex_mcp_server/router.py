from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import httpx


class ModelID(str, Enum):
    PHI3_MINI = "phi3-mini"
    MISTRAL_7B = "mistral-7b"
    LLAMA3_8B = "llama3-8b"
    CODELLAMA_13B = "codellama-13b"
    CLAUDE = "claude"
    OPENAI_GPT5 = "openai-gpt5"
    OPENAI_GPT45 = "openai-gpt45"


class TaskType(str, Enum):
    CLASSIFY_INTENT = "classify_intent"
    PARSE_LOG = "parse_log"
    EXTRACT_ENTITIES = "extract_entities"
    SUMMARIZE_SHORT = "summarize_short"
    VALIDATE_SCHEMA = "validate_schema"
    CLASSIFY_THREAT = "classify_threat"
    DETECT_ANOMALY = "detect_anomaly"
    ANALYZE_ATTACK = "analyze_attack"
    SCORE_RISK = "score_risk"
    CORRELATE_EVENTS = "correlate_events"
    INVESTIGATE = "investigate"
    EXPLAIN = "explain"
    COMPARE_POLICIES = "compare_policies"
    ANSWER_SOC = "answer_soc"
    DRAFT_PLAN = "draft_plan"
    ANALYZE_GRAPH = "analyze_graph"
    GENERATE_REGO = "generate_rego"
    GENERATE_TEST = "generate_rego_test"
    REFACTOR_REGO = "refactor_rego"
    GENERATE_SCRIPT = "generate_script"
    EXPLAIN_CODE = "explain_code"
    COMPLEX_REASONING = "complex_reasoning"
    HIGH_RISK_DECISION = "high_risk_decision"
    HUMAN_EXPLANATION = "human_explanation"


TASK_TO_MODEL: dict[TaskType, tuple[ModelID, ModelID]] = {
    TaskType.CLASSIFY_INTENT: (ModelID.PHI3_MINI, ModelID.MISTRAL_7B),
    TaskType.PARSE_LOG: (ModelID.PHI3_MINI, ModelID.MISTRAL_7B),
    TaskType.EXTRACT_ENTITIES: (ModelID.PHI3_MINI, ModelID.LLAMA3_8B),
    TaskType.SUMMARIZE_SHORT: (ModelID.PHI3_MINI, ModelID.LLAMA3_8B),
    TaskType.VALIDATE_SCHEMA: (ModelID.PHI3_MINI, ModelID.MISTRAL_7B),
    TaskType.CLASSIFY_THREAT: (ModelID.MISTRAL_7B, ModelID.LLAMA3_8B),
    TaskType.DETECT_ANOMALY: (ModelID.MISTRAL_7B, ModelID.LLAMA3_8B),
    TaskType.ANALYZE_ATTACK: (ModelID.MISTRAL_7B, ModelID.LLAMA3_8B),
    TaskType.SCORE_RISK: (ModelID.MISTRAL_7B, ModelID.LLAMA3_8B),
    TaskType.CORRELATE_EVENTS: (ModelID.MISTRAL_7B, ModelID.LLAMA3_8B),
    TaskType.INVESTIGATE: (ModelID.LLAMA3_8B, ModelID.CLAUDE),
    TaskType.EXPLAIN: (ModelID.LLAMA3_8B, ModelID.CLAUDE),
    TaskType.COMPARE_POLICIES: (ModelID.LLAMA3_8B, ModelID.CLAUDE),
    TaskType.ANSWER_SOC: (ModelID.LLAMA3_8B, ModelID.CLAUDE),
    TaskType.DRAFT_PLAN: (ModelID.LLAMA3_8B, ModelID.CLAUDE),
    TaskType.ANALYZE_GRAPH: (ModelID.LLAMA3_8B, ModelID.CLAUDE),
    TaskType.GENERATE_REGO: (ModelID.CODELLAMA_13B, ModelID.CLAUDE),
    TaskType.GENERATE_TEST: (ModelID.CODELLAMA_13B, ModelID.CLAUDE),
    TaskType.REFACTOR_REGO: (ModelID.CODELLAMA_13B, ModelID.CLAUDE),
    TaskType.GENERATE_SCRIPT: (ModelID.CODELLAMA_13B, ModelID.CLAUDE),
    TaskType.EXPLAIN_CODE: (ModelID.CODELLAMA_13B, ModelID.LLAMA3_8B),
    TaskType.COMPLEX_REASONING: (ModelID.OPENAI_GPT5, ModelID.CLAUDE),
    TaskType.HIGH_RISK_DECISION: (ModelID.CLAUDE, ModelID.OPENAI_GPT5),
    TaskType.HUMAN_EXPLANATION: (ModelID.OPENAI_GPT5, ModelID.CLAUDE),
}


MODEL_TIMEOUTS: dict[ModelID, int] = {
    ModelID.PHI3_MINI: 500,
    ModelID.MISTRAL_7B: 3_000,
    ModelID.LLAMA3_8B: 8_000,
    ModelID.CODELLAMA_13B: 20_000,
    ModelID.CLAUDE: 30_000,
    ModelID.OPENAI_GPT5: 30_000,
    ModelID.OPENAI_GPT45: 30_000,
}


@dataclass(slots=True)
class RouterConfig:
    forced_models: dict[TaskType, ModelID] = field(default_factory=dict)
    disabled_models: set[ModelID] = field(default_factory=set)
    routing_confidence_threshold: float = 0.85
    gpu_cloud_enabled: bool = True


@dataclass(slots=True)
class RoutingDecision:
    task_type: TaskType
    primary_model: ModelID
    fallback_model: ModelID
    timeout_ms: int
    hardware: str
    reason: str
    routing_source: str


class CircuitBreaker:
    FAILURE_THRESHOLD = 3

    def __init__(self, model: ModelID):
        self.model = model
        self.failures = 0
        self.state = "closed"

    def is_open(self) -> bool:
        return self.state == "open"

    def record_success(self) -> None:
        self.failures = 0
        self.state = "closed"

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.FAILURE_THRESHOLD:
            self.state = "open"


class SmartModelRouter:
    PHI3_CLASSIFICATION_SYSTEM = """You are a task classifier for a Zero Trust IAM system.
Classify the input into exactly ONE task type from this list.
Reply with ONLY the task type string. No explanation. No punctuation.

Task types:
classify_intent | parse_log | extract_entities | summarize_short | validate_schema |
classify_threat | detect_anomaly | analyze_attack | score_risk | correlate_events |
investigate | explain | compare_policies | answer_soc | draft_plan | analyze_graph |
generate_rego | generate_rego_test | refactor_rego | generate_script | explain_code |
complex_reasoning | high_risk_decision | human_explanation"""

    FAST_PATH_KEYWORDS: dict[str, str] = {
        "generate rego": "generate_rego",
        "write rego": "generate_rego",
        "create policy": "generate_rego",
        "rego test": "generate_rego_test",
        "refactor rego": "refactor_rego",
        "powershell script": "generate_script",
        "ad script": "generate_script",
        "classify threat": "classify_threat",
        "threat event": "classify_threat",
        "anomaly": "detect_anomaly",
        "attack pattern": "analyze_attack",
        "risk score": "score_risk",
        "correlate": "correlate_events",
        "investigate": "investigate",
        "blast radius": "explain",
        "graph path": "analyze_graph",
        "attack path": "analyze_graph",
        "remediation plan": "draft_plan",
        "parse log": "parse_log",
        "extract entities": "extract_entities",
        "summarize": "summarize_short",
        "bloodhound": "analyze_graph",
        "tier 0": "analyze_graph",
        "tier0": "analyze_graph",
        "privilege path": "analyze_graph",
        "privileged path": "analyze_graph",
        "acl path": "analyze_graph",
        "group membership risk": "analyze_graph",
        "blast radius ad": "analyze_graph",
        "resource exposure": "analyze_graph",
        "visualize exposure": "analyze_graph",
        "privilege question": "answer_soc",
        "who can reach": "answer_soc",
        "who has path": "answer_soc",
        "ad drift": "investigate",
        "gpo drift": "investigate",
        "stale account": "investigate",
        "orphan object": "investigate",
        "dirsync": "detect_anomaly",
        "ldap drift": "detect_anomaly",
        "kerberoast": "analyze_attack",
        "delegation risk": "analyze_attack",
        "service account": "generate_script",
        "ldap acl": "explain",
        "security descriptor": "explain",
        "restore deleted object": "high_risk_decision",
        "recycle bin restore": "high_risk_decision",
        "decision analysis": "high_risk_decision",
        "high risk decision": "high_risk_decision",
        "approval decision": "high_risk_decision",
        "human approval": "human_explanation",
        "executive summary": "human_explanation",
        "decision memo": "human_explanation",
    }

    def __init__(
        self,
        config: RouterConfig | None = None,
        phi3_endpoint: str = "http://vllm-cpu:8001",
        phi3_api_key: str = "",
    ):
        self.config = config or RouterConfig()
        self.phi3_endpoint = phi3_endpoint
        self.phi3_api_key = phi3_api_key
        self.circuit_breakers = {model: CircuitBreaker(model) for model in ModelID}

    async def route(self, task: str, context: dict[str, object]) -> RoutingDecision:
        task_type, confidence, routing_source = await self._classify_task(task, context)
        primary, fallback = TASK_TO_MODEL.get(task_type, (ModelID.LLAMA3_8B, ModelID.CLAUDE))

        if task_type in self.config.forced_models:
            primary = self.config.forced_models[task_type]

        if not self.config.gpu_cloud_enabled and primary in {ModelID.LLAMA3_8B, ModelID.CODELLAMA_13B}:
            primary = fallback if fallback not in {ModelID.LLAMA3_8B, ModelID.CODELLAMA_13B} else ModelID.CLAUDE

        if primary in self.config.disabled_models or self.circuit_breakers[primary].is_open():
            primary = fallback if fallback not in self.config.disabled_models else ModelID.CLAUDE

        hardware = "cpu_local"
        if primary in {ModelID.LLAMA3_8B, ModelID.CODELLAMA_13B}:
            hardware = "gpu_cloud"
        if primary == ModelID.CLAUDE:
            hardware = "api"

        return RoutingDecision(
            task_type=task_type,
            primary_model=primary,
            fallback_model=fallback,
            timeout_ms=MODEL_TIMEOUTS[primary],
            hardware=hardware,
            reason=f"task={task_type.value},hw={hardware},confidence={confidence:.2f}",
            routing_source=routing_source,
        )

    async def _classify_task(self, task: str, context: dict[str, object]) -> tuple[TaskType, float, str]:
        joined = f"{task} {' '.join(str(v) for v in context.values())}".lower()
        for keyword, task_type in self.FAST_PATH_KEYWORDS.items():
            if keyword in joined:
                return TaskType(task_type), 1.0, "fast_path"

        headers: dict[str, str] = {}
        if self.phi3_api_key:
            headers["Authorization"] = f"Bearer {self.phi3_api_key}"

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await asyncio.wait_for(
                    client.post(
                        f"{self.phi3_endpoint}/v1/chat/completions",
                        json={
                            "model": "phi3-mini",
                            "messages": [
                                {"role": "system", "content": self.PHI3_CLASSIFICATION_SYSTEM},
                                {
                                    "role": "user",
                                    "content": f"Task: {task[:300]}\nContext keys: {list(context.keys())[:5]}",
                                },
                            ],
                            "max_tokens": 15,
                            "temperature": 0.05,
                            "stream": False,
                            "stop": ["\n", " ", "|"],
                        },
                        headers=headers,
                    ),
                    timeout=2.0,
                )
                response.raise_for_status()
                raw = response.json()["choices"][0]["message"]["content"].strip().lower().replace("-", "_")
                valid = {item.value for item in TaskType}
                if raw in valid:
                    return TaskType(raw), 0.9, "phi3"
        except Exception:
            pass

        return self._heuristic_classify(joined), 0.5, "heuristic"

    def _heuristic_classify(self, task_lower: str) -> TaskType:
        if any(kw in task_lower for kw in ("rego", "policy", "script", "code")):
            return TaskType.GENERATE_REGO
        if any(kw in task_lower for kw in ("threat", "attack", "anomaly", "risk")):
            return TaskType.CLASSIFY_THREAT
        if any(kw in task_lower for kw in ("investigate", "incident", "explain")):
            return TaskType.INVESTIGATE
        if any(kw in task_lower for kw in ("parse", "extract", "log", "summarize")):
            return TaskType.PARSE_LOG
        return TaskType.COMPLEX_REASONING
