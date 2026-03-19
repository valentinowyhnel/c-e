"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

type MachineRecord = {
  id: string;
  label: string;
  kind: string;
  status: "healthy" | "degraded" | "unreachable";
  relatedEdges: number;
  alerts: number;
  trustHint: number;
};

type HealthResponse = Record<
  string,
  {
    status?: "healthy" | "degraded" | "unreachable";
    latency?: number;
  }
>;

type FeedEvent = {
  id: string;
  service?: string;
  severity?: number;
};

type GraphPayload = {
  nodes: Array<{ id: string; type?: string; displayName?: string }>;
  edges: Array<{ source: string; target: string; type: string }>;
};

async function loadFleet() {
  const [graphResp, healthResp, feedResp] = await Promise.all([
    fetch("/api/graph/overview", { cache: "no-store" }),
    fetch("/api/obs/health", { cache: "no-store" }),
    fetch("/api/obs/feed", { cache: "no-store" })
  ]);

  return {
    graph: (graphResp.ok ? await graphResp.json() : { nodes: [], edges: [] }) as GraphPayload,
    health: (healthResp.ok ? await healthResp.json() : {}) as HealthResponse,
    feed: (feedResp.ok ? await feedResp.json() : []) as FeedEvent[]
  };
}

function toMachineRecords(
  graph: GraphPayload,
  health: HealthResponse,
  feed: FeedEvent[]
): MachineRecord[] {
  const interestingTypes = new Set(["Device", "Service", "Agent", "AIAgent"]);

  return graph.nodes
    .filter((node) => interestingTypes.has(node.type ?? ""))
    .map((node) => {
      const key = Object.keys(health).find((name) =>
        [node.id, node.displayName ?? ""].some((value) =>
          value.toLowerCase().includes(name.replace("cortex-", "").toLowerCase())
        )
      );
      const serviceHealth = key ? health[key] : undefined;
      const alerts = feed.filter((event) => {
        const marker = (event.service ?? "").toLowerCase();
        const target = `${node.id} ${node.displayName ?? ""}`.toLowerCase();
        return marker && target.includes(marker.replace("cortex-", "")) && (event.severity ?? 0) >= 3;
      }).length;

      return {
        id: node.id,
        label: node.displayName ?? node.id,
        kind: node.type ?? "Unknown",
        status: serviceHealth?.status ?? "unreachable",
        relatedEdges: graph.edges.filter(
          (edge) => edge.source === node.id || edge.target === node.id
        ).length,
        alerts,
        trustHint: Math.max(8, 96 - alerts * 14 - (serviceHealth?.status === "degraded" ? 22 : 0))
      };
    })
    .sort((left, right) => right.alerts - left.alerts || right.relatedEdges - left.relatedEdges);
}

export function MachineFleetPanel() {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["machine-fleet"],
    queryFn: loadFleet,
    refetchInterval: 5_000
  });

  const machines = useMemo(
    () => (data ? toMachineRecords(data.graph, data.health, data.feed) : []),
    [data]
  );

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return machines;
    }
    return machines.filter((machine) =>
      `${machine.id} ${machine.label} ${machine.kind}`.toLowerCase().includes(needle)
    );
  }, [machines, query]);

  const selected =
    filtered.find((machine) => machine.id === selectedId) ?? filtered[0] ?? machines[0] ?? null;

  return (
    <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
      <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Machine Fleet
            </h2>
            <p className="mt-1 text-sm text-muted">
              Services, agents et machines exposes avec score de friction operateur.
            </p>
          </div>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filtrer machine ou agent"
            className="w-full max-w-xs rounded-xl border border-border/70 bg-background/50 px-3 py-2 text-sm text-ink outline-none"
          />
        </div>

        <div className="mt-4 max-h-[34rem] space-y-2 overflow-auto pr-1">
          {filtered.map((machine) => {
            const active = selected?.id === machine.id;
            const dot =
              machine.status === "healthy"
                ? "bg-green-500"
                : machine.status === "degraded"
                  ? "bg-amber-500"
                  : "bg-red-500";

            return (
              <button
                key={machine.id}
                type="button"
                onClick={() => setSelectedId(machine.id)}
                className={`w-full rounded-2xl border p-3 text-left transition ${
                  active
                    ? "border-cyan-400/60 bg-cyan-400/10"
                    : "border-border/70 bg-background/35 hover:border-cyan-500/30"
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-ink">{machine.label}</div>
                    <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                      {machine.kind} | {machine.id}
                    </div>
                  </div>
                  <span className={`h-3 w-3 rounded-full ${dot}`} />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 font-mono text-xs text-muted">
                  <span>alerts={machine.alerts}</span>
                  <span>edges={machine.relatedEdges}</span>
                  <span>trust~{machine.trustHint}</span>
                </div>
              </button>
            );
          })}
          {!filtered.length ? (
            <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
              Aucun composant correspondant au filtre.
            </div>
          ) : null}
        </div>
      </div>

      <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
        {selected ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
                  Focus machine
                </div>
                <h3 className="mt-2 text-2xl font-semibold text-ink">{selected.label}</h3>
              </div>
              <div className="rounded-full border border-border/70 px-3 py-1 font-mono text-xs text-muted">
                {selected.kind}
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
                <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                  Health status
                </div>
                <div className="mt-3 text-3xl font-semibold text-ink">{selected.status}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
                <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                  Related edges
                </div>
                <div className="mt-3 text-3xl font-semibold text-ink">{selected.relatedEdges}</div>
              </div>
              <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
                <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                  Trust hint
                </div>
                <div className="mt-3 text-3xl font-semibold text-ink">{selected.trustHint}</div>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-border/70 bg-background/30 p-4">
              <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                Operator reading
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">
                Cette vue relie topologie, sante service et pression evenementielle. Elle sert a
                reperer vite les machines degradees, les agents sous forte activite et les services
                dont le graphe de dependance grossit anormalement.
              </p>
            </div>
          </>
        ) : (
          <div className="flex h-full min-h-[28rem] items-center justify-center rounded-2xl border border-dashed border-border/70 text-sm text-muted">
            Aucune machine disponible.
          </div>
        )}
      </div>
    </section>
  );
}
