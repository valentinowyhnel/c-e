"use client";

import { useMemo } from "react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

type ProviderId = "vllm_local" | "anthropic" | "openai";

type GovernanceResponse = {
  updatedAt: string | null;
  mcpReachable: boolean;
  agents: Array<{
    id: string;
    label: string;
    description: string;
    tasks: string[];
  }>;
  assignments: Record<string, Record<string, string>>;
  taskReports: Array<{
    agentId: string;
    task: string;
    modelId: string | null;
    supported: boolean;
    ready: boolean;
    preferred: boolean;
  }>;
  agentStatuses: Array<{
    agentId: string;
    installed: boolean;
    status: "healthy" | "degraded" | "missing";
    readyTasks: number;
    totalTasks: number;
    modelsInUse: string[];
    providersInUse: ProviderId[];
    issueCount: number;
    headline: string;
  }>;
  providerStatuses: Array<{
    providerId: ProviderId;
    configured: boolean;
    reachable: boolean;
    status: "healthy" | "degraded" | "missing";
    headline: string;
    detail: string;
  }>;
  trainingProfiles: Array<{
    agentId: string;
    focus: string[];
    noveltyPolicy: string[];
    unsafeFilters: string[];
  }>;
  trainingSources: Array<{
    id: string;
    label: string;
    status: "implemented" | "partial" | "roadmap";
    description: string;
    path: string;
    routedTo: string[];
  }>;
  summary: {
    agentsCovered: number;
    totalAgents: number;
    readyTasks: number;
    totalTasks: number;
    verifiedModels: number;
    totalModels: number;
  };
};

const STATUS_TONE = {
  healthy: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  degraded: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  missing: "border-slate-500/40 bg-slate-500/10 text-slate-200"
} as const;

const SOURCE_TONE = {
  implemented: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  partial: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  roadmap: "border-slate-500/40 bg-slate-500/10 text-slate-200"
} as const;

function prettyTask(task: string) {
  return task.replaceAll("_", " ");
}

function prettyProvider(providerId: ProviderId) {
  if (providerId === "vllm_local") return "vLLM local";
  if (providerId === "anthropic") return "Anthropic";
  return "OpenAI";
}

async function loadGovernance(): Promise<GovernanceResponse> {
  const response = await fetch("/api/model-governance", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("model-governance unavailable");
  }
  return response.json();
}

async function mutateGovernance(method: "POST" | "PUT", body?: unknown): Promise<GovernanceResponse> {
  const response = await fetch("/api/model-governance", {
    method,
    cache: "no-store",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    throw new Error(`model-governance ${method.toLowerCase()} failed`);
  }
  return response.json();
}

export function AgentsOperationsPanel() {
  const [actionPending, setActionPending] = useState<"revalidate" | "dry-run-defaults" | "apply-defaults" | null>(null);
  const [actionBanner, setActionBanner] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data, error, refetch } = useQuery({
    queryKey: ["agents-operations-panel"],
    queryFn: loadGovernance,
    refetchInterval: 10_000
  });

  const profileByAgent = useMemo(
    () => new Map((data?.trainingProfiles ?? []).map((profile) => [profile.agentId, profile])),
    [data]
  );
  const agentById = useMemo(() => new Map((data?.agents ?? []).map((agent) => [agent.id, agent])), [data]);
  const reportsByAgent = useMemo(() => {
    const map = new Map<string, GovernanceResponse["taskReports"]>();
    for (const report of data?.taskReports ?? []) {
      const existing = map.get(report.agentId) ?? [];
      existing.push(report);
      map.set(report.agentId, existing);
    }
    return map;
  }, [data]);

  const implementedSources = data?.trainingSources.filter((source) => source.status === "implemented").length ?? 0;
  const degradedAgents = data?.agentStatuses.filter((agent) => agent.status !== "healthy").length ?? 0;
  const healthyProviders = data?.providerStatuses.filter((provider) => provider.status === "healthy").length ?? 0;
  const fallbackAssignments = useMemo(() => {
    const next: Record<string, Record<string, string>> = {};
    for (const agent of data?.agents ?? []) {
      next[agent.id] = {};
      for (const task of agent.tasks) {
        const report = data?.taskReports.find((item) => item.agentId === agent.id && item.task === task);
        next[agent.id][task] = report?.modelId ?? "";
      }
    }
    return next;
  }, [data]);

  async function revalidateRuntime() {
    setActionPending("revalidate");
    setActionBanner(null);
    setActionError(null);
    try {
      const next = await mutateGovernance("POST", { assignments: fallbackAssignments });
      await refetch();
      setActionBanner(
        `Revalidation terminee: ${next.summary.readyTasks}/${next.summary.totalTasks} taches pretes, ${next.summary.agentsCovered}/${next.summary.totalAgents} agents couverts.`
      );
    } catch (mutationError) {
      setActionError(mutationError instanceof Error ? mutationError.message : "Revalidation failed");
    } finally {
      setActionPending(null);
    }
  }

  async function dryRunRecommendedBindings() {
    setActionPending("dry-run-defaults");
    setActionBanner(null);
    setActionError(null);
    try {
      const recommended = Object.fromEntries(
        (data?.agents ?? []).map((agent) => [
          agent.id,
          Object.fromEntries(
            agent.tasks.map((task) => {
              const preferredReport = data?.taskReports.find(
                (report) => report.agentId === agent.id && report.task === task && report.supported
              );
              return [task, preferredReport?.modelId ?? ""];
            })
          )
        ])
      );
      const next = await mutateGovernance("POST", { assignments: recommended });
      setActionBanner(
        `Dry-run termine: projection a ${next.summary.readyTasks}/${next.summary.totalTasks} taches pretes avant toute ecriture.`
      );
    } catch (mutationError) {
      setActionError(mutationError instanceof Error ? mutationError.message : "Dry-run failed");
    } finally {
      setActionPending(null);
    }
  }

  async function applyRecommendedBindings() {
    setActionPending("apply-defaults");
    setActionBanner(null);
    setActionError(null);
    try {
      const recommended = Object.fromEntries(
        (data?.agents ?? []).map((agent) => [
          agent.id,
          Object.fromEntries(
            agent.tasks.map((task) => {
              const preferredReport = data?.taskReports.find(
                (report) => report.agentId === agent.id && report.task === task && report.supported
              );
              return [task, preferredReport?.modelId ?? ""];
            })
          )
        ])
      );
      const next = await mutateGovernance("PUT", { assignments: recommended });
      await refetch();
      setActionBanner(
        `Bindings recommandes appliques: ${next.summary.readyTasks}/${next.summary.totalTasks} taches pretes apres ecriture.`
      );
    } catch (mutationError) {
      setActionError(mutationError instanceof Error ? mutationError.message : "Apply failed");
    } finally {
      setActionPending(null);
    }
  }

  return (
    <section className="space-y-6">
      <div className="agents-rail rounded-3xl border border-white/10 p-5 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Agent Runtime</div>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Lecture operationnelle des agents Cortex</h2>
            <p className="mt-2 max-w-3xl text-sm text-muted">
              Cette vue relie installation logique, readiness des taches, providers actifs et garde-fous de
              curation. Elle sert a verifier que la chaine agentique reste exploitable sans ouvrir la voie a
              un apprentissage offensif ou a des bindings opaques.
            </p>
          </div>
          <div className="rounded-full border border-border/70 bg-background/30 px-3 py-1 font-mono text-xs text-muted">
            {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : "never validated"}
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-4">
          <div className="metric-tile rounded-2xl border border-border/70 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Agents healthy</div>
            <div className="mt-3 text-3xl font-semibold text-ink">
              {data?.summary.agentsCovered ?? 0}/{data?.summary.totalAgents ?? 0}
            </div>
          </div>
          <div className="metric-tile rounded-2xl border border-border/70 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Agents a revoir</div>
            <div className="mt-3 text-3xl font-semibold text-ink">{degradedAgents}</div>
          </div>
          <div className="metric-tile rounded-2xl border border-border/70 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Providers healthy</div>
            <div className="mt-3 text-3xl font-semibold text-ink">
              {healthyProviders}/{data?.providerStatuses.length ?? 0}
            </div>
          </div>
          <div className="metric-tile rounded-2xl border border-border/70 p-4">
            <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Sources implementees</div>
            <div className="mt-3 text-3xl font-semibold text-ink">
              {implementedSources}/{data?.trainingSources.length ?? 0}
            </div>
            <div className="mt-2 text-sm text-muted">MCP {data?.mcpReachable ? "reachable" : "degraded"}</div>
          </div>
        </div>

        <div className="mt-5 rounded-[1.6rem] border border-cyan-500/20 bg-cyan-500/5 p-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan-200">Operator Actions</div>
              <h3 className="mt-2 text-xl font-semibold text-ink">Commandes directes depuis la vue Agents</h3>
              <p className="mt-2 max-w-3xl text-sm text-muted">
                Les actions ci-dessous restent fail-closed: revalidation en lecture, dry-run avant retour aux
                bindings recommandes, puis application explicite seulement apres projection.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void revalidateRuntime()}
                disabled={actionPending !== null}
                className="rounded-2xl border border-border/70 bg-background/30 px-4 py-2 text-sm font-semibold text-ink transition hover:border-cyan-500/40 disabled:opacity-60"
              >
                {actionPending === "revalidate" ? "Revalidation..." : "Revalider maintenant"}
              </button>
              <button
                type="button"
                onClick={() => void dryRunRecommendedBindings()}
                disabled={actionPending !== null}
                className="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm font-semibold text-amber-100 transition hover:bg-amber-500/20 disabled:opacity-60"
              >
                {actionPending === "dry-run-defaults" ? "Dry-run..." : "Dry-run bindings recommandes"}
              </button>
              <button
                type="button"
                onClick={() => void applyRecommendedBindings()}
                disabled={actionPending !== null}
                className="rounded-2xl border border-cyan-400/50 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20 disabled:opacity-60"
              >
                {actionPending === "apply-defaults" ? "Application..." : "Appliquer bindings recommandes"}
              </button>
            </div>
          </div>

          {actionBanner ? (
            <div className="mt-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
              {actionBanner}
            </div>
          ) : null}

          {actionError ? (
            <div className="mt-4 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
              {actionError}
            </div>
          ) : null}
        </div>

        {error ? (
          <div className="mt-5 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            Impossible de charger l&apos;etat operationnel des agents.
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.88fr_1.12fr]">
        <div className="space-y-6">
          <div className="runtime-card rounded-3xl border border-white/10 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Provider Runtime</div>
            <h3 className="mt-2 text-2xl font-semibold text-ink">Etat des providers relies aux agents</h3>
            <div className="mt-5 space-y-3">
              {data?.providerStatuses.map((provider) => (
                <div key={provider.providerId} className={`panel-sheen rounded-2xl border p-4 ${STATUS_TONE[provider.status]}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{prettyProvider(provider.providerId)}</div>
                      <div className="mt-1 text-sm opacity-90">{provider.headline}</div>
                    </div>
                    <span className="rounded-full border border-current/30 px-2.5 py-1 font-mono text-xs uppercase tracking-[0.2em]">
                      {provider.status}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs opacity-90">
                    <span className="rounded-full border border-current/20 px-2.5 py-1">
                      {provider.configured ? "configured" : "not configured"}
                    </span>
                    <span className="rounded-full border border-current/20 px-2.5 py-1">
                      {provider.reachable ? "reachable" : "not reachable"}
                    </span>
                  </div>
                  <div className="mt-3 text-sm opacity-90">{provider.detail}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="runtime-card rounded-3xl border border-white/10 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Training Sources</div>
            <h3 className="mt-2 text-2xl font-semibold text-ink">Routage des sources defensives</h3>
            <div className="mt-5 space-y-3">
              {data?.trainingSources.map((source) => (
                <div key={source.id} className="rounded-2xl border border-border/70 bg-background/25 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-ink">{source.label}</div>
                      <div className="mt-1 text-sm text-muted">{source.description}</div>
                    </div>
                    <span className={`rounded-full border px-3 py-1 font-mono text-xs ${SOURCE_TONE[source.status]}`}>
                      {source.status}
                    </span>
                  </div>
                  <div className="mt-3 rounded-xl border border-border/60 bg-[#081321]/60 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                    {source.path}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {source.routedTo.map((agentId) => (
                      <span key={`${source.id}-${agentId}`} className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100">
                        {agentById.get(agentId)?.label ?? agentId}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="runtime-card rounded-3xl border border-white/10 p-5 shadow-panel">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Agent Matrix</div>
                <h3 className="mt-2 text-2xl font-semibold text-ink">Etat detaille par agent</h3>
                <p className="mt-2 text-sm text-muted">
                  Chaque carte expose la sante runtime, les bindings reels, les providers engages et les garde-fous
                  de curation associes a l&apos;agent.
                </p>
              </div>
              <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-right">
                <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan-200">Task coverage</div>
                <div className="mt-2 text-2xl font-semibold text-ink">
                  {data?.summary.readyTasks ?? 0}/{data?.summary.totalTasks ?? 0}
                </div>
              </div>
            </div>

            <div className="mt-5 grid gap-4 xl:grid-cols-2">
              {data?.agentStatuses.map((status) => {
                const agent = agentById.get(status.agentId);
                const profile = profileByAgent.get(status.agentId);
                const reports = reportsByAgent.get(status.agentId) ?? [];

                return (
                  <div key={status.agentId} className="panel-sheen rounded-[1.6rem] border border-border/70 bg-background/25 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan-300">{status.agentId}</div>
                        <div className="mt-2 text-lg font-semibold text-ink">{agent?.label ?? status.agentId}</div>
                        <div className="mt-1 text-sm text-muted">{agent?.description}</div>
                      </div>
                      <span className={`rounded-full border px-3 py-1 font-mono text-xs ${STATUS_TONE[status.status]}`}>
                        {status.status}
                      </span>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                      <div className="metric-tile rounded-xl border border-border/60 px-3 py-3">
                        <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">Tasks ready</div>
                        <div className="mt-2 text-2xl font-semibold text-ink">
                          {status.readyTasks}/{status.totalTasks}
                        </div>
                      </div>
                      <div className="metric-tile rounded-xl border border-border/60 px-3 py-3">
                        <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">Models in use</div>
                        <div className="mt-2 text-2xl font-semibold text-ink">{status.modelsInUse.length}</div>
                      </div>
                      <div className="metric-tile rounded-xl border border-border/60 px-3 py-3">
                        <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">Issues</div>
                        <div className="mt-2 text-2xl font-semibold text-ink">{status.issueCount}</div>
                      </div>
                    </div>

                    <div className="mt-4 text-sm text-muted">{status.headline}</div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {status.providersInUse.map((providerId) => (
                        <span key={`${status.agentId}-${providerId}`} className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100 signal-glow">
                          {prettyProvider(providerId)}
                        </span>
                      ))}
                      {!status.providersInUse.length ? (
                        <span className="rounded-full border border-border/70 bg-background/30 px-2.5 py-1 text-xs text-muted">
                          no provider bound
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-4 space-y-2">
                      {reports.map((report) => (
                        <div key={`${report.agentId}-${report.task}`} className="rounded-xl border border-border/60 bg-[#081321]/60 px-3 py-3">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <div className="text-sm font-semibold text-ink">{prettyTask(report.task)}</div>
                              <div className="mt-1 text-xs text-muted">{report.modelId ?? "Aucun modele lie"}</div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <span
                                className={`rounded-full border px-2.5 py-1 font-mono text-xs ${
                                  report.ready
                                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                                    : "border-amber-500/40 bg-amber-500/10 text-amber-200"
                                }`}
                              >
                                {report.ready ? "ready" : "check"}
                              </span>
                              <span
                                className={`rounded-full border px-2.5 py-1 font-mono text-xs ${
                                  report.supported
                                    ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-100"
                                    : "border-rose-500/40 bg-rose-500/10 text-rose-200"
                                }`}
                              >
                                {report.supported ? "aligned" : "out-of-scope"}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    {profile ? (
                      <div className="mt-4 grid gap-3 md:grid-cols-2">
                        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-3">
                          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-amber-100">Novelty policy</div>
                          <div className="mt-2 space-y-2 text-sm text-amber-100">
                            {profile.noveltyPolicy.slice(0, 2).map((item) => (
                              <div key={`${status.agentId}-novelty-${item}`}>{item}</div>
                            ))}
                          </div>
                        </div>
                        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-3">
                          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-rose-100">Unsafe filters</div>
                          <div className="mt-2 space-y-2 text-sm text-rose-100">
                            {profile.unsafeFilters.slice(0, 2).map((item) => (
                              <div key={`${status.agentId}-unsafe-${item}`}>{item}</div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
