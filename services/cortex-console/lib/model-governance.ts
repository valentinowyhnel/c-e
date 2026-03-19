import { readOperatorState, writeOperatorState } from "@/lib/operator-state";
import { readModelKeys, type ModelKeys } from "@/lib/vault-model-keys";

const GOVERNANCE_SCOPE = "model-governance";
const DEFAULT_MCP_URL = process.env.CORTEX_MCP_SERVER_URL ?? "http://cortex-mcp-server:8080";

export type ProviderId = "vllm_local" | "anthropic" | "openai";

export type ModelDefinition = {
  id: string;
  label: string;
  provider: ProviderId;
  role: string;
  requiresKey: boolean;
  preferredFor: string[];
};

export type AgentDefinition = {
  id: string;
  label: string;
  description: string;
  tasks: string[];
};

export type GovernanceState = {
  assignments: Record<string, Record<string, string>>;
  updatedAt: string | null;
};

type ModelProbe = {
  modelId: string;
  status: "verified" | "missing_key" | "unreachable" | "unknown";
  detail: string;
};

type TaskReport = {
  agentId: string;
  task: string;
  modelId: string | null;
  supported: boolean;
  ready: boolean;
  preferred: boolean;
};

type ValidationIssue = {
  level: "error" | "warning";
  message: string;
  agentId?: string;
  task?: string;
  modelId?: string;
};

export const MODEL_DEFINITIONS: ModelDefinition[] = [
  { id: "phi3-mini", label: "Phi-3 Mini", provider: "vllm_local", role: "Routing et classification courte", requiresKey: false, preferredFor: ["request_classification", "tool_routing", "schema_validation", "telemetry_summarization"] },
  { id: "mistral-7b", label: "Mistral 7B", provider: "vllm_local", role: "Menaces, anomalies, correlation", requiresKey: false, preferredFor: ["threat_classification", "anomaly_detection", "event_correlation", "resource_pressure_analysis"] },
  { id: "llama3-8b", label: "Llama 3 8B", provider: "vllm_local", role: "Analyse et investigation", requiresKey: false, preferredFor: ["incident_investigation", "attack_path_analysis", "blast_radius_analysis", "privilege_path_analysis", "remediation_plan", "soc_question_answering", "ad_drift_analysis", "gpo_drift_review"] },
  { id: "codellama-13b", label: "CodeLlama 13B", provider: "vllm_local", role: "Scripts AD et generation controlee", requiresKey: false, preferredFor: ["directory_script_generation", "code_generation", "restore_deleted_review"] },
  { id: "claude-sonnet-4", label: "Claude Sonnet 4", provider: "anthropic", role: "Decision humaine et risque eleve", requiresKey: true, preferredFor: ["high_risk_decision", "decision_human_explanation", "privilege_change_review", "apoptosis_explanation", "gpo_drift_review"] },
  { id: "gpt-5", label: "GPT-5", provider: "openai", role: "Analyse decisionnelle large", requiresKey: true, preferredFor: ["decision_analysis", "privilege_change_review", "incident_investigation", "remediation_plan"] },
  { id: "gpt-4.5", label: "GPT-4.5", provider: "openai", role: "Synthese et explication", requiresKey: true, preferredFor: ["decision_human_explanation", "blast_radius_analysis", "service_account_review", "soc_question_answering"] }
];

export const AGENT_DEFINITIONS: AgentDefinition[] = [
  { id: "decision", label: "Decision Agent", description: "Arbitrage Claude, GPT et synthese humaine.", tasks: ["decision_analysis", "decision_human_explanation", "high_risk_decision", "privilege_change_review"] },
  { id: "ad", label: "AD Agent", description: "BloodHound, privilege paths, drift et service accounts.", tasks: ["ad_drift_analysis", "privilege_path_analysis", "service_account_review", "gpo_drift_review", "restore_deleted_review", "directory_script_generation"] },
  { id: "remediation", label: "Remediation Agent", description: "Blast radius, quarantine, apoptosis et plans de correction.", tasks: ["remediation_plan", "blast_radius_analysis", "apoptosis_explanation", "privilege_change_review"] },
  { id: "soc", label: "SOC Agent", description: "Investigation, reponse aux analystes et chemins d'attaque.", tasks: ["threat_classification", "incident_investigation", "attack_path_analysis", "soc_question_answering"] },
  { id: "observer", label: "Observer Agent", description: "Correlation continue et suivi ressources.", tasks: ["event_correlation", "anomaly_detection", "resource_pressure_analysis", "telemetry_summarization"] },
  { id: "mcp-router", label: "MCP Router", description: "Selection de modele et garantie schema / tools.", tasks: ["request_classification", "tool_routing", "schema_validation", "code_generation"] }
];

const PROVIDER_LABELS: Record<ProviderId, string> = {
  vllm_local: "vLLM local / cluster",
  anthropic: "Anthropic",
  openai: "OpenAI"
};

function modelById(modelId: string) {
  return MODEL_DEFINITIONS.find((model) => model.id === modelId) ?? null;
}

function maskKey(value: string) {
  if (!value) return "";
  if (value.length <= 8) return `${value.slice(0, 2)}***${value.slice(-1)}`;
  return `${value.slice(0, 4)}***${value.slice(-4)}`;
}

export function defaultAssignments() {
  return Object.fromEntries(
    AGENT_DEFINITIONS.map((agent) => [
      agent.id,
      Object.fromEntries(
        agent.tasks.map((task) => {
          const preferred = MODEL_DEFINITIONS.find((model) => model.preferredFor.includes(task));
          return [task, preferred?.id ?? ""];
        })
      )
    ])
  );
}

export async function readGovernanceState(): Promise<GovernanceState> {
  const fallback: GovernanceState = { assignments: defaultAssignments(), updatedAt: null };
  const state = await readOperatorState<GovernanceState>(GOVERNANCE_SCOPE, fallback);
  return { assignments: { ...defaultAssignments(), ...(state.assignments ?? {}) }, updatedAt: state.updatedAt ?? null };
}

export async function writeGovernanceState(next: Partial<GovernanceState>) {
  const current = await readGovernanceState();
  const merged: GovernanceState = {
    assignments: { ...current.assignments, ...(next.assignments ?? {}) },
    updatedAt: new Date().toISOString()
  };
  await writeOperatorState(GOVERNANCE_SCOPE, merged);
  return merged;
}

async function probeMcp() {
  try {
    const response = await fetch(`${DEFAULT_MCP_URL}/healthz`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

async function probeModel(model: ModelDefinition, keys: ModelKeys, mcpReachable: boolean): Promise<ModelProbe> {
  if (model.provider === "vllm_local") {
    return { modelId: model.id, status: mcpReachable ? "verified" : "unknown", detail: mcpReachable ? "MCP reachable, model dispatch available." : "MCP health unknown from console." };
  }
  const key = keys[model.provider];
  if (!key) {
    return { modelId: model.id, status: "missing_key", detail: `Cle ${PROVIDER_LABELS[model.provider]} absente.` };
  }
  const validFormat = model.provider === "anthropic" ? key.startsWith("sk-ant-") : key.startsWith("sk-");
  return { modelId: model.id, status: validFormat ? "verified" : "unreachable", detail: validFormat ? "Format de cle valide." : "Format de cle inattendu." };
}

export async function buildGovernanceView(state: GovernanceState) {
  const keyState = await readModelKeys();
  const keys = keyState.keys;
  const taskReports: TaskReport[] = [];
  const issues: ValidationIssue[] = [];
  const mcpReachable = await probeMcp();

  for (const agent of AGENT_DEFINITIONS) {
    const assigned = state.assignments[agent.id] ?? {};
    for (const task of agent.tasks) {
      const modelId = assigned[task] ?? null;
      const model = modelId ? modelById(modelId) : null;
      const supported = Boolean(model && model.preferredFor.includes(task));
      const ready = Boolean(model && supported && (!model.requiresKey || keys[model.provider]));
      const preferred = supported;

      if (!modelId) {
        issues.push({ level: "error", agentId: agent.id, task, message: `Aucun modele lie a ${task}.` });
      } else if (!model) {
        issues.push({ level: "error", agentId: agent.id, task, modelId, message: `Modele inconnu: ${modelId}.` });
      } else if (!supported) {
        issues.push({ level: "error", agentId: agent.id, task, modelId, message: `${model.label} n'est pas aligne avec la tache ${task}.` });
      } else if (model.requiresKey && !keys[model.provider]) {
        issues.push({ level: "warning", agentId: agent.id, task, modelId, message: `${model.label} est lie a ${task} mais la cle ${PROVIDER_LABELS[model.provider]} est absente.` });
      }

      taskReports.push({ agentId: agent.id, task, modelId, supported, ready, preferred });
    }
  }

  const modelProbes = await Promise.all(MODEL_DEFINITIONS.map((model) => probeModel(model, keys, mcpReachable)));
  const usedModelIds = new Set(taskReports.map((report) => report.modelId).filter(Boolean));

  for (const probe of modelProbes) {
    if (usedModelIds.has(probe.modelId) && probe.status !== "verified") {
      issues.push({ level: probe.status === "missing_key" ? "warning" : "error", modelId: probe.modelId, message: `${probe.modelId}: ${probe.detail}` });
    }
  }

  return {
    updatedAt: state.updatedAt,
    mcpReachable,
    keyBackend: {
      source: keyState.source,
      writable: keyState.writable
    },
    providers: Object.entries(PROVIDER_LABELS).map(([id, label]) => {
      const providerId = id as ProviderId;
      const configured = Boolean(keys[providerId]);
      return { id: providerId, label, configured, maskedKey: configured ? maskKey(keys[providerId] ?? "") : "", models: MODEL_DEFINITIONS.filter((model) => model.provider === providerId).map((model) => model.id) };
    }),
    models: MODEL_DEFINITIONS,
    agents: AGENT_DEFINITIONS,
    assignments: state.assignments,
    taskReports,
    modelProbes,
    issues,
    summary: {
      agentsCovered: AGENT_DEFINITIONS.filter((agent) => agent.tasks.every((task) => taskReports.some((report) => report.agentId === agent.id && report.task === task && report.ready))).length,
      totalAgents: AGENT_DEFINITIONS.length,
      readyTasks: taskReports.filter((report) => report.ready).length,
      totalTasks: taskReports.length,
      verifiedModels: modelProbes.filter((probe) => probe.status === "verified").length,
      totalModels: modelProbes.length
    }
  };
}
