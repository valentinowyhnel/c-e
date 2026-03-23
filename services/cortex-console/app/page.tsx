"use client";

import { useQuery } from "@tanstack/react-query";

import { ApprovalPanel } from "@/components/approval-panel";
import { DecisionTheater } from "@/components/decision-theater";
import { IdentityGraph } from "@/components/identity-graph";
import { IntelligenceFeed } from "@/components/intelligence-feed";
import { KpiCard } from "@/components/kpi-card";
import { MachineFleetPanel } from "@/components/machine-fleet-panel";
import { ServiceHealthGrid } from "@/components/service-health-grid";
import { SchemaExplorer } from "@/components/schema-explorer";
import { SOTPanel } from "@/components/sot-panel";
import type { DashboardState } from "@/lib/types";

async function loadDashboard(): Promise<DashboardState> {
  const response = await fetch("/api/dashboard", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("dashboard fetch failed");
  }
  return response.json();
}

export default function DashboardPage() {
  const { data } = useQuery({
    queryKey: ["dashboard"],
    queryFn: loadDashboard,
    refetchInterval: 10_000
  });

  if (!data) {
    return <main className="p-8 text-muted">Chargement de la console SOC...</main>;
  }

  return (
    <main className="min-h-screen p-4 md:p-8">
      <ApprovalPanel />
      <SOTPanel />

      <div className="mx-auto max-w-7xl space-y-6">
        <header className="hero-frame panel-sheen rounded-[2rem] p-6 md:p-8">
          <div className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="font-mono text-[11px] uppercase tracking-[0.35em] text-cyan-300">
                  {data.criticalAlerts > 0 ? "Critical Decision Pressure" : "Operational Stability"}
                </div>
                <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                  p99 trust {data.trustEngineLatencyP99}ms
                </div>
              </div>
              <h1 className="mt-5 max-w-4xl text-4xl font-semibold leading-tight text-ink md:text-5xl">
                Cortex SOC Console
                <span className="block text-cyan-200/90">pilotage tactique du trust, des machines et des decisions.</span>
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-7 text-muted">
                Surface operateur pour lire le systeme, arbitrer les approvals, suivre les graphes de privileges
                et absorber les signaux agentiques sans perdre la latence du fast path.
              </p>
            </div>

            <div className="grid gap-3 self-start">
              <div className="rounded-[1.6rem] border border-white/10 bg-black/20 p-4">
                <div className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted">Operational pulse</div>
                <div className="mt-4 grid gap-3">
                  <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-panel/60 px-4 py-3">
                    <span className="text-sm text-muted">critical alerts</span>
                    <span className="font-mono text-xl text-red-200">{data.criticalAlerts}</span>
                  </div>
                  <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-panel/60 px-4 py-3">
                    <span className="text-sm text-muted">pending approvals</span>
                    <span className="font-mono text-xl text-amber-100">{data.pendingApprovals}</span>
                  </div>
                  <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-panel/60 px-4 py-3">
                    <span className="text-sm text-muted">sentinel blocked</span>
                    <span className="font-mono text-xl text-cyan-100">{data.sentinelBlocked}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <div className="rounded-2xl border border-border/70 bg-black/15 px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">trust</div>
            <div className="mt-2 text-sm text-ink">engine p99 {data.trustEngineLatencyP99} ms</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-black/15 px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">policy</div>
            <div className="mt-2 text-sm text-ink">{data.policyDecisionsPerSec} decisions/sec</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-black/15 px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">graph</div>
            <div className="mt-2 text-sm text-ink">{data.graphNodesTotal.toLocaleString()} nodes</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-black/15 px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">mcp</div>
            <div className="mt-2 text-sm text-ink">{data.mcpCallsLast1h} calls / 1h</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-black/15 px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">ad sync</div>
            <div className="mt-2 text-sm text-ink">{data.adSyncDeltaPending} delta pending</div>
          </div>
          <div className="rounded-2xl border border-border/70 bg-black/15 px-4 py-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">maturity</div>
            <div className="mt-2 text-sm text-ink">{data.capabilityMaturitySummary?.beta ?? 0} beta caps</div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            title="Sessions actives"
            value={String(data.activeSessionsCount)}
            subtitle="sessions operateur et workflows live"
            eyebrow="activity"
          />
          <KpiCard
            title="Trust < 40"
            value={String(data.usersWithLowTrust)}
            tone="warning"
            subtitle="identites sous seuil critique"
            eyebrow="exposure"
          />
          <KpiCard
            title="Anomalies"
            value={String(data.criticalAlerts)}
            tone={data.criticalAlerts > 0 ? "danger" : "success"}
            subtitle="signal agrégé du feed agentique"
            eyebrow="signal"
          />
          <KpiCard
            title="Approbations"
            value={String(data.pendingApprovals)}
            tone="danger"
            subtitle={`${data.approvalsPendingOldest} min plus ancienne`}
            eyebrow="governance"
          />
        </section>

        {data.degradedWarnings?.length ? (
          <section className="panel-sheen rounded-3xl border border-amber-500/50 bg-amber-500/10 p-4 shadow-panel">
            <div className="font-mono text-xs uppercase tracking-[0.3em] text-amber-200">
              Degraded Warnings
            </div>
            <div className="mt-3 grid gap-2">
              {data.degradedWarnings.map((warning) => (
                <div key={warning} className="rounded-2xl border border-amber-500/40 bg-black/10 p-3 text-sm text-amber-50">
                  {warning}
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <IntelligenceFeed />
          <ServiceHealthGrid />
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <IdentityGraph />
          <div className="panel-sheen rounded-[1.8rem] border bg-panel/80 p-5 shadow-panel">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Agentic Snapshot
            </h2>
            <div className="grid gap-3">
              {[
                ["trust latency", `${data.trustEngineLatencyP99} ms`],
                ["ext_authz latency", `${data.extAuthzLatencyP99} ms`],
                ["agent tasks / 1h", `${data.agentTasksLast1h}`],
                ["mcp calls observed", `${data.mcpCallsLast1h}`],
                ["graph nodes", `${data.graphNodesTotal.toLocaleString()}`],
                ["prepare plans", `${data.executionModeSummary?.prepare ?? 0}`],
                ["beta capabilities", `${data.capabilityMaturitySummary?.beta ?? 0}`]
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between rounded-2xl border border-border/70 bg-background/35 px-4 py-3 font-mono text-sm">
                  <span className="text-muted">{label}</span>
                  <span className="text-ink">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <MachineFleetPanel />
        <DecisionTheater />
        <SchemaExplorer />
      </div>
    </main>
  );
}
