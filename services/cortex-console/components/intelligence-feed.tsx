"use client";

import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

type IntelligenceEvent = {
  id: string;
  timestamp: number;
  type: "anomaly" | "action" | "forecast" | "pattern" | "health";
  severity: 1 | 2 | 3 | 4 | 5;
  service: string;
  title: string;
  explanation: string;
  action_taken?: string;
  requires_approval?: boolean;
  approval_id?: string;
};

const severityConfig = {
  1: { label: "INFO", className: "text-sky-300 bg-sky-950/30" },
  2: { label: "WARN", className: "text-amber-300 bg-amber-950/30" },
  3: { label: "ERROR", className: "text-orange-300 bg-orange-950/30" },
  4: { label: "CRIT", className: "text-red-300 bg-red-950/40" },
  5: { label: "EMERG", className: "text-red-200 bg-red-900/60" }
} as const;

async function loadFeed(): Promise<IntelligenceEvent[]> {
  const response = await fetch("/api/obs/feed", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("obs feed fetch failed");
  }
  return response.json();
}

export function IntelligenceFeed() {
  const { data = [] } = useQuery({
    queryKey: ["obs-feed"],
    queryFn: loadFeed,
    refetchInterval: 5000
  });

  return (
    <div className="rounded-2xl border bg-panel/80 shadow-panel">
      <div className="flex items-center justify-between border-b border-border/70 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
            Intelligence Feed
          </h2>
          <p className="mt-1 text-xs font-mono text-muted">
            Vue agentique de l'etat Cortex
          </p>
        </div>
        <span className="font-mono text-xs text-muted">{data.length} events</span>
      </div>

      <div className="max-h-[34rem] divide-y divide-border/50 overflow-auto">
        {data.map((event) => {
          const config = severityConfig[event.severity];
          return (
            <div key={event.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-2 py-1 font-mono text-xs font-bold ${config.className}`}>
                    {config.label}
                  </span>
                  <span className="font-mono text-xs text-muted">
                    {formatDistanceToNow(new Date(event.timestamp * 1000), {
                      addSuffix: true,
                      locale: fr
                    })}
                  </span>
                </div>
                <span className="rounded border border-border/70 px-2 py-1 font-mono text-xs text-muted">
                  {event.service}
                </span>
              </div>

              <p className="mt-3 text-sm font-medium text-ink">{event.title}</p>
              <p className="mt-1 text-sm text-muted">{event.explanation}</p>

              {event.action_taken ? (
                <div className="mt-2 font-mono text-xs text-green-300">
                  Action autonome: {event.action_taken}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
