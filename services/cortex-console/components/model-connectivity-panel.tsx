"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

type ProviderId = "vllm_local" | "anthropic" | "openai";

type GovernanceResponse = {
  updatedAt: string | null;
  mcpReachable: boolean;
  keyBackend: {
    source: string;
    writable: boolean;
  };
  providers: Array<{
    id: ProviderId;
    label: string;
    configured: boolean;
    maskedKey: string;
    models: string[];
  }>;
  models: Array<{
    id: string;
    label: string;
    provider: ProviderId;
    role: string;
    requiresKey: boolean;
    preferredFor: string[];
  }>;
  taskReports: Array<{
    agentId: string;
    task: string;
    modelId: string | null;
    supported: boolean;
    ready: boolean;
    preferred: boolean;
  }>;
  modelProbes: Array<{
    modelId: string;
    status: "verified" | "missing_key" | "unreachable" | "unknown";
    detail: string;
  }>;
  issues: Array<{
    level: "error" | "warning";
    message: string;
    modelId?: string;
  }>;
  summary: {
    readyTasks: number;
    totalTasks: number;
    verifiedModels: number;
    totalModels: number;
  };
};

type ProviderAudit = {
  id: ProviderId;
  label: string;
  configured: boolean;
  maskedKey: string;
  status: "verified" | "warning" | "critical";
  headline: string;
  models: Array<{
    id: string;
    label: string;
    status: "verified" | "missing_key" | "unreachable" | "unknown";
    detail: string;
    role: string;
    tasksBacked: number;
  }>;
  checklist: string[];
};

const STATUS_TONE = {
  verified: "border-emerald-500/40 bg-emerald-500/10 text-emerald-100",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-100",
  critical: "border-rose-500/40 bg-rose-500/10 text-rose-100"
} as const;

const PROBE_TONE = {
  verified: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  missing_key: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  unreachable: "border-rose-500/40 bg-rose-500/10 text-rose-200",
  unknown: "border-slate-500/40 bg-slate-500/10 text-slate-200"
} as const;

async function loadGovernance(): Promise<GovernanceResponse> {
  const response = await fetch("/api/model-governance", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("model-governance unavailable");
  }
  return response.json();
}

function buildProviderAudit(data: GovernanceResponse): ProviderAudit[] {
  const probesByModel = new Map(data.modelProbes.map((probe) => [probe.modelId, probe]));
  const tasksByModel = new Map<string, number>();

  for (const report of data.taskReports) {
    if (!report.modelId) continue;
    tasksByModel.set(report.modelId, (tasksByModel.get(report.modelId) ?? 0) + 1);
  }

  return data.providers.map((provider) => {
    const models = data.models
      .filter((model) => model.provider === provider.id)
      .map((model) => {
        const probe = probesByModel.get(model.id);
        return {
          id: model.id,
          label: model.label,
          status: probe?.status ?? "unknown",
          detail: probe?.detail ?? "No probe detail.",
          role: model.role,
          tasksBacked: tasksByModel.get(model.id) ?? 0
        };
      });

    const hasCritical = models.some((model) => model.status === "unreachable");
    const hasWarning = models.some((model) => model.status === "missing_key" || model.status === "unknown");
    const status = hasCritical ? "critical" : hasWarning ? "warning" : "verified";
    const headline =
      status === "verified"
        ? "Connection chain validated."
        : status === "critical"
          ? "Provider chain broken or unverifiable."
          : "Provider partially configured.";

    const checklist: string[] = [];
    if (provider.id === "vllm_local") {
      checklist.push(data.mcpReachable ? "MCP reachable from console." : "MCP unreachable from console.");
      checklist.push(models.every((model) => model.tasksBacked > 0) ? "Each local model backs at least one task." : "Some local models are defined but not currently bound.");
    } else if (provider.id === "anthropic") {
      checklist.push(provider.configured ? `Anthropic key detected (${provider.maskedKey}).` : "Anthropic key missing.");
      checklist.push(models.every((model) => model.status === "verified") ? "Claude API key format validated." : "Claude key format or probe state requires attention.");
      checklist.push(models.some((model) => model.tasksBacked > 0) ? "Claude is linked to live decision tasks." : "Claude is not linked to any active task.");
    } else {
      checklist.push(provider.configured ? `OpenAI key detected (${provider.maskedKey}).` : "OpenAI key missing.");
      checklist.push(models.every((model) => model.status === "verified") ? "OpenAI key format validated for GPT models." : "OpenAI key format or probe state requires attention.");
      checklist.push(models.some((model) => model.tasksBacked > 0) ? "GPT models are linked to active tasks." : "GPT models are not linked to any active task.");
    }

    return {
      id: provider.id,
      label: provider.label,
      configured: provider.configured,
      maskedKey: provider.maskedKey,
      status,
      headline,
      models,
      checklist
    };
  });
}

function statusLabel(status: ProviderAudit["status"]) {
  if (status === "verified") return "verified";
  if (status === "warning") return "needs review";
  return "critical";
}

export function ModelConnectivityPanel() {
  const { data, error } = useQuery({
    queryKey: ["model-governance-connectivity"],
    queryFn: loadGovernance,
    refetchInterval: 10_000
  });

  const providerAudits = useMemo(() => (data ? buildProviderAudit(data) : []), [data]);
  const claudeAudit = providerAudits.find((provider) => provider.id === "anthropic");
  const openAiAudit = providerAudits.find((provider) => provider.id === "openai");

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
              Model Connectivity
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-ink">
              Verification rigoureuse de la connexion des modeles
            </h2>
            <p className="mt-2 max-w-3xl text-sm text-muted">
              Cette section valide la chaine utile de connexion: backend de cles, reachability MCP,
              affectation agent/tache, format de cle attendu et sonde par modele. Le statut est
              donc exploitable pour l&apos;operationnel, pas seulement cosmetique.
            </p>
          </div>
          <Link
            href="/models"
            className="rounded-2xl border border-cyan-400/50 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20"
          >
            Gerer les cles et bindings
          </Link>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Modeles verifies</div>
            <div className="mt-3 text-3xl font-semibold text-ink">
              {data?.summary.verifiedModels ?? 0}/{data?.summary.totalModels ?? 0}
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Taches prêtes</div>
            <div className="mt-3 text-3xl font-semibold text-ink">
              {data?.summary.readyTasks ?? 0}/{data?.summary.totalTasks ?? 0}
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">MCP dispatch</div>
            <div
              className={`mt-3 inline-flex rounded-full border px-3 py-1 font-mono text-xs ${
                data?.mcpReachable
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                  : "border-rose-500/40 bg-rose-500/10 text-rose-200"
              }`}
            >
              {data?.mcpReachable ? "reachable" : "degraded"}
            </div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Key backend</div>
            <div className="mt-3 text-sm font-semibold text-ink">
              {data?.keyBackend.source ?? "unknown"} {data?.keyBackend.writable ? "rw" : "ro"}
            </div>
          </div>
        </div>

        {error ? (
          <div className="mt-5 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            Impossible de charger la gouvernance des modeles.
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        {[claudeAudit, openAiAudit].map((provider) =>
          provider ? (
            <div key={provider.id} className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
                    {provider.id === "anthropic" ? "Claude API" : "ChatGPT / OpenAI API"}
                  </div>
                  <h3 className="mt-2 text-2xl font-semibold text-ink">{provider.label}</h3>
                  <p className="mt-2 text-sm text-muted">{provider.headline}</p>
                </div>
                <span className={`rounded-full border px-3 py-1 font-mono text-xs ${STATUS_TONE[provider.status]}`}>
                  {statusLabel(provider.status)}
                </span>
              </div>

              <div className="mt-5 grid gap-3">
                {provider.checklist.map((item) => (
                  <div key={item} className="rounded-2xl border border-border/70 bg-background/30 px-4 py-3 text-sm text-ink">
                    {item}
                  </div>
                ))}
              </div>

              <div className="mt-5 space-y-3">
                {provider.models.map((model) => (
                  <div key={model.id} className={`rounded-2xl border px-4 py-3 ${PROBE_TONE[model.status]}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold">{model.label}</div>
                        <div className="mt-1 text-xs opacity-90">{model.role}</div>
                      </div>
                      <div className="text-right font-mono text-[11px] uppercase tracking-[0.2em]">
                        {model.status} · tasks {model.tasksBacked}
                      </div>
                    </div>
                    <div className="mt-2 text-sm opacity-90">{model.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null
        )}
      </div>

      <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">All Models</div>
            <h3 className="mt-2 text-2xl font-semibold text-ink">Etat de connexion par modele</h3>
            <p className="mt-2 text-sm text-muted">
              Chaque modele est audite avec sa sonde actuelle. Un modele non verifie ici ne doit
              pas etre considere comme fiable pour la chaine de decision.
            </p>
          </div>
          <div className="rounded-full border border-border/70 bg-background/30 px-3 py-1 font-mono text-xs text-muted">
            {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : "never validated"}
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {providerAudits.flatMap((provider) =>
            provider.models.map((model) => (
              <div key={model.id} className={`rounded-2xl border px-4 py-4 ${PROBE_TONE[model.status]}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold">{model.label}</div>
                    <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.2em] opacity-80">
                      {provider.label}
                    </div>
                  </div>
                  <span className="rounded-full border border-current/30 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em]">
                    {model.status}
                  </span>
                </div>
                <div className="mt-3 text-sm opacity-90">{model.detail}</div>
                <div className="mt-4 grid gap-2 text-xs opacity-90">
                  <div className="flex items-center justify-between">
                    <span>Role</span>
                    <span className="text-right">{model.role}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Bound tasks</span>
                    <span className="font-mono">{model.tasksBacked}</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {(data?.issues?.length ?? 0) > 0 ? (
          <div className="mt-5 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-amber-100">
              Validation issues
            </div>
            <div className="mt-3 space-y-2">
              {data?.issues.slice(0, 8).map((issue, index) => (
                <div key={`${issue.message}-${index}`} className="text-sm text-amber-100">
                  {issue.message}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
