"use client";

import { useEffect, useMemo, useState } from "react";

type ProviderInfo = {
  id: "vllm_local" | "anthropic" | "openai";
  label: string;
  configured: boolean;
  maskedKey: string;
  models: string[];
};

type ModelInfo = {
  id: string;
  label: string;
  provider: ProviderInfo["id"];
  role: string;
  requiresKey: boolean;
  preferredFor: string[];
};

type AgentInfo = {
  id: string;
  label: string;
  description: string;
  tasks: string[];
};

type TaskReport = {
  agentId: string;
  task: string;
  modelId: string | null;
  supported: boolean;
  ready: boolean;
  preferred: boolean;
};

type ModelProbe = {
  modelId: string;
  status: "verified" | "missing_key" | "unreachable" | "unknown";
  detail: string;
};

type GovernanceResponse = {
  updatedAt: string | null;
  mcpReachable: boolean;
  keyBackend: {
    source: string;
    writable: boolean;
  };
  providers: ProviderInfo[];
  models: ModelInfo[];
  agents: AgentInfo[];
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
  assignments: Record<string, Record<string, string>>;
  taskReports: TaskReport[];
  modelProbes: ModelProbe[];
  issues: Array<{
    level: "error" | "warning";
    message: string;
    agentId?: string;
    task?: string;
    modelId?: string;
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

const STATUS_TONE: Record<ModelProbe["status"], string> = {
  verified: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  missing_key: "border-amber-500/40 bg-amber-500/10 text-amber-200",
  unreachable: "border-rose-500/40 bg-rose-500/10 text-rose-200",
  unknown: "border-slate-500/40 bg-slate-500/10 text-slate-200"
};

function prettyTask(task: string) {
  return task.replaceAll("_", " ");
}

async function fetchGovernance(method: "GET" | "PUT" | "POST", body?: unknown) {
  const response = await fetch("/api/model-governance", {
    method,
    cache: "no-store",
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });

  if (!response.ok) {
    throw new Error(`model-governance ${method} failed`);
  }

  return (await response.json()) as GovernanceResponse;
}

export function ModelKeyControl() {
  const [data, setData] = useState<GovernanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [draftAssignments, setDraftAssignments] = useState<Record<string, Record<string, string>>>({});

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const next = await fetchGovernance("GET");
        if (!cancelled) {
          setData(next);
          setDraftAssignments(next.assignments);
          setError(null);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Loading failed");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void load();
    const timer = window.setInterval(load, 12_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const modelsByTask = useMemo(() => {
    const map = new Map<string, ModelInfo[]>();
    for (const model of data?.models ?? []) {
      for (const task of model.preferredFor) {
        const existing = map.get(task) ?? [];
        existing.push(model);
        map.set(task, existing);
      }
    }
    return map;
  }, [data]);

  const probesByModel = useMemo(() => new Map((data?.modelProbes ?? []).map((probe) => [probe.modelId, probe])), [data]);
  const taskReportByKey = useMemo(
    () => new Map((data?.taskReports ?? []).map((report) => [`${report.agentId}:${report.task}`, report])),
    [data]
  );

  const save = async () => {
    setSaving(true);
    setBanner(null);
    try {
      const next = await fetchGovernance("PUT", { keys: draftKeys, assignments: draftAssignments });
      setData(next);
      setDraftAssignments(next.assignments);
      setDraftKeys({});
      setError(null);
      setBanner("Configuration enregistree et revalidee.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const validate = async () => {
    setValidating(true);
    setBanner(null);
    try {
      const next = await fetchGovernance("POST", { keys: draftKeys, assignments: draftAssignments });
      setData(next);
      setError(null);
      setBanner("Validation terminee. Verifie les alertes avant application.");
    } catch (validationError) {
      setError(validationError instanceof Error ? validationError.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  if (loading && !data) {
    return (
      <section className="rounded-3xl border bg-panel/80 p-6 text-sm text-muted shadow-panel">
        Chargement des liaisons modeles...
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-4">
        <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
          <div className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">Agents couverts</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {data?.summary.agentsCovered}/{data?.summary.totalAgents}
          </div>
        </div>
        <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
          <div className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">Taches prêtes</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {data?.summary.readyTasks}/{data?.summary.totalTasks}
          </div>
        </div>
        <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
          <div className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">Modeles verifies</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {data?.summary.verifiedModels}/{data?.summary.totalModels}
          </div>
        </div>
        <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
          <div className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">Vault backend</div>
          <div
            className={`mt-3 inline-flex rounded-full border px-3 py-1 text-sm ${
              data?.keyBackend.writable
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                : "border-amber-500/40 bg-amber-500/10 text-amber-200"
            }`}
          >
            {data?.keyBackend.source} {data?.keyBackend.writable ? "rw" : "ro"}
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.92fr_1.08fr]">
        <div className="space-y-6">
          <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Model Access</div>
                <h2 className="mt-2 text-2xl font-semibold text-ink">Cles API et verification</h2>
                <p className="mt-2 text-sm text-muted">
                  Chaque provider est conserve cote serveur, masque en lecture et revalide avant usage agentique.
                </p>
                <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                  backend {data?.keyBackend.source} · mcp {data?.mcpReachable ? "reachable" : "degraded"}
                </p>
              </div>
              <div className="rounded-full border border-border/70 bg-background/30 px-3 py-1 font-mono text-xs text-muted">
                {data?.updatedAt ? new Date(data.updatedAt).toLocaleString() : "jamais enregistre"}
              </div>
            </div>

            <div className="mt-5 space-y-4">
              {data?.providers.map((provider) => (
                <div key={provider.id} className="rounded-2xl border border-border/70 bg-background/25 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-ink">{provider.label}</div>
                      <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                        {provider.models.join(" · ")}
                      </div>
                    </div>
                    <span
                      className={`rounded-full border px-2.5 py-1 font-mono text-xs ${
                        provider.configured
                          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                          : "border-border/70 bg-background/30 text-muted"
                      }`}
                    >
                      {provider.configured ? provider.maskedKey : "no key"}
                    </span>
                  </div>

                  <label className="mt-4 block">
                    <span className="mb-2 block text-xs uppercase tracking-[0.2em] text-muted">Nouvelle cle</span>
                    <input
                      type="password"
                      value={draftKeys[provider.id] ?? ""}
                      onChange={(event) => setDraftKeys((current) => ({ ...current, [provider.id]: event.target.value }))}
                      placeholder={provider.id === "vllm_local" ? "Aucune cle requise" : "Colle une cle pour mise a jour"}
                      className="w-full rounded-2xl border border-border/70 bg-[#081321] px-3 py-3 text-sm text-ink outline-none transition placeholder:text-muted focus:border-cyan-500/50"
                      disabled={provider.id === "vllm_local"}
                    />
                  </label>
                </div>
              ))}
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={save}
                disabled={saving || !data?.keyBackend.writable}
                className="rounded-2xl border border-cyan-400/50 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20 disabled:opacity-60"
              >
                {saving ? "Enregistrement..." : "Enregistrer"}
              </button>
              <button
                type="button"
                onClick={validate}
                disabled={validating}
                className="rounded-2xl border border-border/70 bg-background/30 px-4 py-2 text-sm font-semibold text-ink transition hover:border-cyan-500/40 disabled:opacity-60"
              >
                {validating ? "Validation..." : "Revalider"}
              </button>
            </div>

            {!data?.keyBackend.writable ? (
              <div className="mt-4 rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                Vault est en lecture seule depuis cette console. Configure `CORTEX_VAULT_ADDR` et `CORTEX_VAULT_TOKEN`
                pour activer l'ecriture des cles depuis l'interface.
              </div>
            ) : null}

            {banner ? (
              <div className="mt-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                {banner}
              </div>
            ) : null}
            {error ? (
              <div className="mt-4 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                {error}
              </div>
            ) : null}
          </div>

          <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Model Probes</div>
            <div className="mt-4 space-y-3">
              {data?.modelProbes.map((probe) => (
                <div key={probe.modelId} className={`rounded-2xl border px-4 py-3 ${STATUS_TONE[probe.status]}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold">{probe.modelId}</div>
                    <div className="font-mono text-[11px] uppercase tracking-[0.2em]">{probe.status}</div>
                  </div>
                  <div className="mt-2 text-sm opacity-90">{probe.detail}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Agent / task binding</div>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Liaison explicite des taches</h2>
            <p className="mt-2 text-sm text-muted">
              Les selections ci-dessous definissent le modele utilise par agent et par tache. Le controle bloque les liaisons hors competence.
            </p>

            <div className="mt-5 space-y-5">
              {data?.agents.map((agent) => (
                <div key={agent.id} className="rounded-2xl border border-border/70 bg-background/25 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold text-ink">{agent.label}</div>
                      <div className="mt-1 text-sm text-muted">{agent.description}</div>
                    </div>
                    <span className="rounded-full border border-border/70 bg-background/30 px-3 py-1 font-mono text-xs text-muted">
                      {agent.id}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3">
                    {agent.tasks.map((task) => {
                      const candidates = modelsByTask.get(task) ?? [];
                      const selected = draftAssignments[agent.id]?.[task] ?? "";
                      const report = taskReportByKey.get(`${agent.id}:${task}`);
                      const selectedProbe = selected ? probesByModel.get(selected) : null;

                      return (
                        <div
                          key={task}
                          className="grid gap-3 rounded-2xl border border-border/60 bg-[#081321]/70 p-3 md:grid-cols-[1fr_18rem_auto] md:items-center"
                        >
                          <div>
                            <div className="text-sm font-semibold text-ink">{prettyTask(task)}</div>
                            <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                              {candidates.map((model) => model.label).join(" · ") || "aucun modele compatible"}
                            </div>
                          </div>

                          <select
                            value={selected}
                            onChange={(event) =>
                              setDraftAssignments((current) => ({
                                ...current,
                                [agent.id]: { ...(current[agent.id] ?? {}), [task]: event.target.value }
                              }))
                            }
                            className="rounded-2xl border border-border/70 bg-background/30 px-3 py-3 text-sm text-ink outline-none transition focus:border-cyan-500/50"
                          >
                            <option value="">Selectionner un modele</option>
                            {candidates.map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.label} · {model.role}
                              </option>
                            ))}
                          </select>

                          <div className="flex flex-wrap gap-2 md:justify-end">
                            <span
                              className={`rounded-full border px-2.5 py-1 font-mono text-xs ${
                                report?.ready
                                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                                  : "border-amber-500/40 bg-amber-500/10 text-amber-200"
                              }`}
                            >
                              {report?.ready ? "ready" : "check"}
                            </span>
                            {selectedProbe ? (
                              <span className={`rounded-full border px-2.5 py-1 font-mono text-xs ${STATUS_TONE[selectedProbe.status]}`}>
                                {selectedProbe.status}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Validation report</div>
            <div className="mt-4 space-y-3">
              {(data?.issues ?? []).map((issue, index) => (
                <div
                  key={`${issue.message}-${index}`}
                  className={`rounded-2xl border px-4 py-3 ${
                    issue.level === "error"
                      ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
                      : "border-amber-500/40 bg-amber-500/10 text-amber-200"
                  }`}
                >
                  <div className="font-mono text-[11px] uppercase tracking-[0.2em]">
                    {issue.level}
                    {issue.agentId ? ` · ${issue.agentId}` : ""}
                    {issue.task ? ` · ${issue.task}` : ""}
                  </div>
                  <div className="mt-2 text-sm">{issue.message}</div>
                </div>
              ))}
              {!data?.issues.length ? (
                <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                  Toutes les taches ont un modele aligne et verifiable.
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Training hardening</div>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Corpus defensif par agent</h2>
            <p className="mt-2 text-sm text-muted">
              Cortex n&apos;ingere pas aveuglement du contenu d&apos;attaque. Chaque agent a un focus utile, une politique
              de nouveaute et des filtres qui bloquent les contenus offensifs deja connus ou trop dangereux.
            </p>

            <div className="mt-5 space-y-4">
              {data?.trainingProfiles.map((profile) => (
                <div key={profile.agentId} className="rounded-2xl border border-border/70 bg-background/25 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-lg font-semibold text-ink">{profile.agentId}</div>
                    <span className="rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 font-mono text-xs text-cyan-100">
                      curated
                    </span>
                  </div>
                  <div className="mt-4 grid gap-4 md:grid-cols-3">
                    <div>
                      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">Focus</div>
                      <div className="mt-2 space-y-2 text-sm text-ink">
                        {profile.focus.map((item) => (
                          <div key={item} className="rounded-xl border border-border/60 bg-[#081321]/60 px-3 py-2">
                            {item}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">Novelty policy</div>
                      <div className="mt-2 space-y-2 text-sm text-amber-100">
                        {profile.noveltyPolicy.map((item) => (
                          <div key={item} className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                            {item}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">Unsafe filters</div>
                      <div className="mt-2 space-y-2 text-sm text-rose-100">
                        {profile.unsafeFilters.map((item) => (
                          <div key={item} className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2">
                            {item}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Internal intelligence sources</div>
            <h2 className="mt-2 text-2xl font-semibold text-ink">Sources internes branchees</h2>
            <p className="mt-2 text-sm text-muted">
              Les agents ne sont enrichis qu&apos;a partir de sources internes normalisees et curées. La source n&apos;accorde
              jamais de droit d&apos;execution; elle alimente uniquement la connaissance defensive.
            </p>
            <div className="mt-5 space-y-3">
              {data?.trainingSources.map((source) => (
                <div key={source.id} className="rounded-2xl border border-border/70 bg-background/25 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold text-ink">{source.label}</div>
                      <div className="mt-1 text-sm text-muted">{source.description}</div>
                    </div>
                    <span
                      className={`rounded-full border px-3 py-1 font-mono text-xs ${
                        source.status === "implemented"
                          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                          : source.status === "partial"
                            ? "border-amber-500/40 bg-amber-500/10 text-amber-200"
                            : "border-border/70 bg-background/30 text-muted"
                      }`}
                    >
                      {source.status}
                    </span>
                  </div>
                  <div className="mt-3 rounded-xl border border-border/60 bg-[#081321]/60 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                    {source.path}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {source.routedTo.map((agent) => (
                      <span key={agent} className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-100">
                        {agent}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
