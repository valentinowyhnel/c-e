"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

import type { ApprovalRequest } from "@/lib/types";

async function loadApprovals(): Promise<ApprovalRequest[]> {
  const response = await fetch("/api/approvals", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("approval fetch failed");
  }
  return response.json();
}

export function ApprovalPanel() {
  const [pendingId, setPendingId] = useState<string | null>(null);
  const { data = [] } = useQuery({
    queryKey: ["approvals"],
    queryFn: loadApprovals,
    refetchInterval: 10_000
  });

  async function approve(requestId: string) {
    setPendingId(requestId);
    try {
      const response = await fetch(`/api/approvals/${requestId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: "Approved via Cortex console" })
      });
      if (!response.ok) {
        throw new Error("approval failed");
      }
    } finally {
      setPendingId(null);
    }
  }

  async function reject(requestId: string) {
    setPendingId(requestId);
    try {
      const response = await fetch(`/api/approvals/${requestId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Rejected via Cortex console" })
      });
      if (!response.ok) {
        throw new Error("rejection failed");
      }
    } finally {
      setPendingId(null);
    }
  }

  if (data.length === 0) {
    return null;
  }

  return (
    <div className="fixed right-4 top-4 z-50 w-[24rem] space-y-3">
      {data.map((req) => {
        const deadline = new Date(req.deadlineTs * 1000);
        const urgent = req.deadlineTs - Date.now() / 1000 < 300;
        return (
          <div
            key={req.requestId}
            className={`rounded-2xl border bg-panel/95 p-4 shadow-panel backdrop-blur ${
              req.riskLevel === 5 ? "border-danger/70" : "border-warning/60"
            } ${urgent ? "animate-pulse" : ""}`}
          >
            <div className="mb-2 flex items-center justify-between">
              <span
                className={`font-mono text-xs font-bold ${
                  req.riskLevel === 5 ? "text-red-400" : "text-amber-300"
                }`}
              >
                RISQUE {req.riskLevel} | {req.approversRequired} approbation(s)
              </span>
              <span className="text-xs text-muted">
                Expire {formatDistanceToNow(deadline, { locale: fr })}
              </span>
            </div>

            <p className="mb-3 text-sm text-ink">{req.reasoning}</p>

            <div className="mb-3 grid gap-2 text-xs text-muted">
              <div className="flex items-center justify-between">
                <span>mode</span>
                <span className="font-mono text-ink">{req.executionMode ?? "prepare"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>maturity</span>
                <span className="font-mono text-ink">{req.capabilityMaturity ?? "beta"}</span>
              </div>
              {req.degradedMode ? (
                <div className="rounded-md border border-amber-500/60 bg-amber-500/10 px-2 py-1 text-amber-100">
                  Mode degrade actif pour ce plan.
                </div>
              ) : null}
            </div>

            <div className="mb-3 space-y-1">
              {req.actions.map((action) => (
                <div
                  key={action.taskId}
                  className="rounded-md border border-border/80 bg-background/40 px-2 py-1 font-mono text-xs text-ink"
                >
                  [{action.riskLevel}] {action.intent}
                  {action.dryRunRequired ? (
                    <span className="ml-2 text-sky-300">[dry-run]</span>
                  ) : null}
                </div>
              ))}
            </div>

            {req.correlationId ? (
              <div className="mb-3 rounded-md border border-border/70 bg-background/30 px-2 py-1 font-mono text-[11px] text-muted">
                correlation_id={req.correlationId}
              </div>
            ) : null}

            <div className="flex gap-2">
              <button
                disabled={pendingId === req.requestId}
                onClick={() => approve(req.requestId)}
                className="flex-1 rounded-md bg-success px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
              >
                Approuver
              </button>
              <button
                disabled={pendingId === req.requestId}
                onClick={() => reject(req.requestId)}
                className="flex-1 rounded-md border border-danger/70 px-3 py-2 text-xs font-semibold text-red-300 disabled:opacity-60"
              >
                Refuser
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
