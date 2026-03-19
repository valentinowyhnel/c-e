"use client";

import { useQuery } from "@tanstack/react-query";

import type { EventStreamItem } from "@/lib/types";

async function loadEvents(): Promise<EventStreamItem[]> {
  const response = await fetch("/api/events", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("event fetch failed");
  }
  return response.json();
}

export function LiveEventStream() {
  const { data = [] } = useQuery({
    queryKey: ["events"],
    queryFn: loadEvents,
    refetchInterval: 5000
  });

  return (
    <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">Live Event Stream</h2>
        <span className="font-mono text-xs text-muted">{data.length} derniers events</span>
      </div>
      <div className="max-h-80 space-y-2 overflow-auto pr-2">
        {data.map((event) => (
          <div key={event.id} className="rounded-xl border border-border/70 bg-background/40 p-3">
            <div className="flex items-center justify-between gap-4">
              <div className="font-medium text-ink">{event.title}</div>
              <div className="font-mono text-xs text-muted">{event.timestamp}</div>
            </div>
            <div className="mt-1 text-sm text-muted">{event.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
