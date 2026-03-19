"use client";

import { useQuery } from "@tanstack/react-query";

type ServiceStatus = {
  name: string;
  status: "healthy" | "degraded" | "unreachable";
  latency: number;
  trend: "stable" | "improving" | "degrading";
  lastCheck: number;
};

const groups = {
  "Auth & Identity": ["cortex-gateway", "cortex-trust-engine", "cortex-envoy"],
  Agents: ["cortex-obs-agent", "cortex-sentinel"],
  Observabilite: ["cortex-mcp-server", "cortex-victoriametrics"],
  Gouvernance: ["cortex-audit", "cortex-approval"]
};

async function loadHealth(): Promise<Record<string, ServiceStatus>> {
  const response = await fetch("/api/obs/health", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("obs health fetch failed");
  }
  return response.json();
}

export function ServiceHealthGrid() {
  const { data = {} } = useQuery({
    queryKey: ["obs-health"],
    queryFn: loadHealth,
    refetchInterval: 5000
  });

  return (
    <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
      <div className="mb-4">
        <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
          Service Health
        </h2>
        <p className="mt-1 text-xs font-mono text-muted">
          Sante temps reel pilotee par l'agent
        </p>
      </div>

      <div className="space-y-4">
        {Object.entries(groups).map(([group, serviceNames]) => (
          <div key={group}>
            <h3 className="mb-2 text-xs font-mono uppercase tracking-[0.2em] text-muted">
              {group}
            </h3>
            <div className="grid gap-2 md:grid-cols-2">
              {serviceNames.map((name) => {
                const service = data[name];
                const status = service?.status ?? "unreachable";
                const dot =
                  status === "healthy"
                    ? "bg-green-500"
                    : status === "degraded"
                      ? "bg-amber-500"
                      : "bg-red-500";

                return (
                  <div key={name} className="rounded-xl border border-border/70 bg-background/40 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
                        <span className="font-mono text-xs text-ink">{name.replace("cortex-", "")}</span>
                      </div>
                      <span className="font-mono text-xs text-muted">
                        {service ? `${Math.round(service.latency)}ms` : "n/a"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
