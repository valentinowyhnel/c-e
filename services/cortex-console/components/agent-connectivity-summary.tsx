"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

type SummaryResponse = {
  mcpReachable: boolean;
  agentStatuses: Array<{
    agentId: string;
    status: "healthy" | "degraded" | "missing";
  }>;
  providerStatuses: Array<{
    providerId: "vllm_local" | "anthropic" | "openai";
    status: "healthy" | "degraded" | "missing";
  }>;
  summary: {
    agentsCovered: number;
    totalAgents: number;
    verifiedModels: number;
    totalModels: number;
  };
};

async function loadGovernance(): Promise<SummaryResponse> {
  const response = await fetch("/api/model-governance", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("model-governance unavailable");
  }
  return response.json();
}

export function AgentConnectivitySummary() {
  const { data } = useQuery({
    queryKey: ["agent-connectivity-summary"],
    queryFn: loadGovernance,
    refetchInterval: 10_000
  });

  const healthyProviders = data?.providerStatuses.filter((provider) => provider.status === "healthy").length ?? 0;
  const degradedAgents = data?.agentStatuses.filter((agent) => agent.status !== "healthy").length ?? 0;

  return (
    <section className="panel-sheen rounded-[1.8rem] border bg-panel/80 p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Agent Connectivity</div>
          <h2 className="mt-2 text-2xl font-semibold text-ink">Etat des agents et providers IA</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted">
            Vue rapide sur l'installation logique des agents Cortex, la sante des bindings et les providers Claude / GPT.
          </p>
        </div>
        <Link
          href="/agents"
          className="rounded-2xl border border-cyan-400/50 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-500/20"
        >
          Ouvrir la surface dediee
        </Link>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
          <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Agents healthy</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {data?.summary.agentsCovered ?? 0}/{data?.summary.totalAgents ?? 0}
          </div>
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
          <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Providers healthy</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {healthyProviders}/{data?.providerStatuses.length ?? 0}
          </div>
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
          <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">Modeles verifies</div>
          <div className="mt-3 text-3xl font-semibold text-ink">
            {data?.summary.verifiedModels ?? 0}/{data?.summary.totalModels ?? 0}
          </div>
        </div>
        <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
          <div className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">MCP</div>
          <div
            className={`mt-3 inline-flex rounded-full border px-3 py-1 font-mono text-xs ${
              data?.mcpReachable
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
                : "border-rose-500/40 bg-rose-500/10 text-rose-200"
            }`}
          >
            {data?.mcpReachable ? "reachable" : "degraded"}
          </div>
          <div className="mt-2 text-sm text-muted">{degradedAgents} agents a revoir</div>
        </div>
      </div>
    </section>
  );
}
