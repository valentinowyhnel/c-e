"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApprovalRequest } from "@/lib/types";
import { ExecutionGovernancePanel } from "@/components/execution-governance-panel";
import { StateMachinePanel } from "@/components/state-machine-panel";

type FeedEvent = {
  id: string;
  severity?: number;
  service?: string;
  title?: string;
  explanation?: string;
  requires_approval?: boolean;
};

async function loadDecisionState() {
  const [approvalsResp, feedResp, dashboardResp, decisionResp] = await Promise.all([
    fetch("/api/approvals?status=pending", { cache: "no-store" }),
    fetch("/api/obs/feed", { cache: "no-store" }),
    fetch("/api/dashboard", { cache: "no-store" }),
    fetch("/api/decision-surface", { cache: "no-store" })
  ]);

  return {
    approvals: (approvalsResp.ok ? await approvalsResp.json() : []) as ApprovalRequest[],
    feed: (feedResp.ok ? await feedResp.json() : []) as FeedEvent[],
    dashboard: dashboardResp.ok ? await dashboardResp.json() : null,
    decision: decisionResp.ok ? await decisionResp.json() : null
  };
}

const LANES = [
  { name: "Phi-3", role: "classifie", tone: "bg-cyan-500/12 text-cyan-200" },
  { name: "Mistral", role: "menace", tone: "bg-amber-500/12 text-amber-200" },
  { name: "Llama / Code", role: "analyse", tone: "bg-emerald-500/12 text-emerald-200" },
  { name: "Claude / GPT", role: "decision", tone: "bg-rose-500/12 text-rose-200" }
];

export function DecisionTheater() {
  const [filter, setFilter] = useState<"all" | "high" | "approval">("all");
  const { data } = useQuery({
    queryKey: ["decision-state"],
    queryFn: loadDecisionState,
    refetchInterval: 5_000
  });

  const feed = data?.feed ?? [];
  const approvals = data?.approvals ?? [];
  const filteredFeed = useMemo(() => {
    if (filter === "high") {
      return feed.filter((item) => (item.severity ?? 0) >= 4);
    }
    if (filter === "approval") {
      return feed.filter((item) => item.requires_approval);
    }
    return feed;
  }, [feed, filter]);

  return (
    <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Decision Theater
            </h2>
            <p className="mt-1 text-sm text-muted">
              Vue operateur des escalades, arbitrages modeles et approvals.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {[
              ["all", "Tout"],
              ["high", "Critique"],
              ["approval", "Approval"]
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value as "all" | "high" | "approval")}
                className={`rounded-full border px-3 py-1 text-xs font-mono ${
                  filter === value
                    ? "border-cyan-400/60 bg-cyan-400/10 text-cyan-100"
                    : "border-border/70 bg-background/40 text-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-4">
          {LANES.map((lane) => (
            <div key={lane.name} className={`rounded-2xl border border-border/70 p-3 ${lane.tone}`}>
              <div className="font-mono text-[11px] uppercase tracking-[0.2em]">{lane.name}</div>
              <div className="mt-2 text-lg font-semibold">{lane.role}</div>
            </div>
          ))}
        </div>

        <div className="mt-5 max-h-[30rem] space-y-3 overflow-auto pr-1">
          {filteredFeed.map((item) => (
            <div key={item.id} className="rounded-2xl border border-border/70 bg-background/30 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="font-medium text-ink">{item.title ?? item.id}</div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full border border-border/70 px-2 py-1 font-mono text-xs text-muted">
                    sev {item.severity ?? 0}
                  </span>
                  <span className="rounded-full border border-border/70 px-2 py-1 font-mono text-xs text-muted">
                    {item.service ?? "unknown"}
                  </span>
                </div>
              </div>
              <p className="mt-2 text-sm text-muted">{item.explanation ?? "No explanation"}</p>
            </div>
          ))}
          {!filteredFeed.length ? (
            <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
              Aucun evenement pour ce filtre.
            </div>
          ) : null}
        </div>
      </div>

      <ExecutionGovernancePanel />

      <div className="space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
            Approval queue
          </h3>
          <div className="mt-4 space-y-3">
            {approvals.slice(0, 6).map((approval) => (
              <div
                key={approval.requestId}
                className="rounded-2xl border border-border/70 bg-background/35 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-ink">{approval.requestId}</div>
                  <span className="rounded-full border border-border/70 px-2 py-1 font-mono text-xs text-muted">
                    risk {approval.riskLevel}
                  </span>
                </div>
                <p className="mt-2 text-sm text-muted">{approval.reasoning || "No reasoning"}</p>
                <div className="mt-3 grid gap-2 text-xs text-muted">
                  <div className="flex items-center justify-between">
                    <span>mode</span>
                    <span className="font-mono text-ink">{approval.executionMode ?? "prepare"}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>maturity</span>
                    <span className="font-mono text-ink">
                      {approval.capabilityMaturity ?? "beta"}
                    </span>
                  </div>
                  {approval.degradedMode ? (
                    <div className="rounded-md border border-amber-500/60 bg-amber-500/10 px-2 py-1 text-amber-100">
                      degraded mode active
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
            {!approvals.length ? (
              <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
                Aucune approbation en attente.
              </div>
            ) : null}
          </div>
        </div>

        <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
            Decision reading
          </h3>
          <p className="mt-4 text-sm leading-6 text-muted">
            Cette page donne une vue claire de la chaine de decision: detection, routage MCP,
            enrichissement agentique, puis approbation humaine quand le niveau de risque l&apos;exige.
          </p>
        </div>

        <StateMachinePanel />
      </div>
    </section>
  );
}
