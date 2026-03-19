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
        <header className="rounded-3xl border border-danger/60 bg-danger/10 p-4 shadow-panel">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.3em] text-red-300">
                {data.criticalAlerts > 0 ? "ALERTE CRITIQUE" : "SURVEILLANCE ACTIVE"}
              </div>
              <h1 className="mt-2 text-3xl font-semibold text-ink">Cortex SOC Console</h1>
            </div>
            <div className="font-mono text-sm text-muted">
              alertes={data.criticalAlerts} | approvals={data.pendingApprovals} | blocked=
              {data.sentinelBlocked}
            </div>
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard title="Sessions actives" value={String(data.activeSessionsCount)} />
          <KpiCard
            title="Trust < 40"
            value={String(data.usersWithLowTrust)}
            tone="warning"
            subtitle="utilisateurs critiques"
          />
          <KpiCard
            title="Anomalies"
            value={String(data.criticalAlerts)}
            tone={data.criticalAlerts > 0 ? "danger" : "success"}
            subtitle="feed agentique"
          />
          <KpiCard
            title="Approbations"
            value={String(data.pendingApprovals)}
            tone="danger"
            subtitle={`${data.approvalsPendingOldest} min plus ancienne`}
          />
        </section>

        {data.degradedWarnings?.length ? (
          <section className="rounded-3xl border border-amber-500/50 bg-amber-500/10 p-4 shadow-panel">
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
          <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Agentic Snapshot
            </h2>
            <div className="space-y-3 font-mono text-sm">
              <div className="flex justify-between">
                <span className="text-muted">trust latency</span>
                <span>{data.trustEngineLatencyP99} ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">ext_authz latency</span>
                <span>{data.extAuthzLatencyP99} ms</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">agent tasks / 1h</span>
                <span>{data.agentTasksLast1h}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">mcp calls observed</span>
                <span>{data.mcpCallsLast1h}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">graph nodes</span>
                <span>{data.graphNodesTotal.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">prepare plans</span>
                <span>{data.executionModeSummary?.prepare ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">beta capabilities</span>
                <span>{data.capabilityMaturitySummary?.beta ?? 0}</span>
              </div>
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
