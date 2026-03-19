"use client";

import { useQuery } from "@tanstack/react-query";

async function loadDecisionSurface() {
  const response = await fetch("/api/decision-surface", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("decision surface unavailable");
  }
  return response.json();
}

function renderMap(title: string, payload?: Record<string, number>) {
  const entries = Object.entries(payload ?? {});
  return (
    <div className="rounded-2xl border border-border/70 bg-background/30 p-4">
      <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">{title}</div>
      <div className="mt-3 space-y-2">
        {entries.length ? (
          entries.map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-muted">{key}</span>
              <span className="font-mono text-ink">{value}</span>
            </div>
          ))
        ) : (
          <div className="text-sm text-muted">Aucune donnee.</div>
        )}
      </div>
    </div>
  );
}

export function ExecutionGovernancePanel() {
  const { data } = useQuery({
    queryKey: ["decision-surface"],
    queryFn: loadDecisionSurface,
    refetchInterval: 10_000
  });

  return (
    <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
      <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
        <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
          Degraded Modes And Guardrails
        </h2>
        <div className="mt-4 space-y-3">
          {(data?.degradedWarnings ?? []).length ? (
            data.degradedWarnings.map((warning: string) => (
              <div
                key={warning}
                className="rounded-2xl border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-100"
              >
                {warning}
              </div>
            ))
          ) : (
            <div className="rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm text-emerald-100">
              Aucun mode degrade critique remonte par la surface decisionnelle.
            </div>
          )}
        </div>
        <div className="mt-4 rounded-2xl border border-border/70 bg-background/30 p-4 text-sm text-muted">
          Les actions destructives restent bloquees si les dependances critiques ou la maturite
          des capabilities ne satisfont pas la policy.
        </div>
      </div>

      <div className="grid gap-4">
        {renderMap("Execution Modes", data?.executionModeCounts)}
        {renderMap("Capability Maturity", data?.maturityCounts)}
      </div>
    </section>
  );
}
