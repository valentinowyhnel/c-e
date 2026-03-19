"use client";

import { useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import { useQuery } from "@tanstack/react-query";

type DashboardPayload = {
  criticalAlerts?: number;
  pendingApprovals?: number;
  graphNodesTotal?: number;
};

const SCHEMA_TEMPLATES: Record<string, (dashboard: DashboardPayload) => string> = {
  sentinel_evidence: () =>
    JSON.stringify(
      {
        entity_id: "node-01",
        evidences: [
          {
            signal_type: "suspicious_process",
            source: "psutil_process",
            severity: 0.72,
            confidence: 0.7,
            ttl_seconds: 300
          }
        ]
      },
      null,
      2
    ),
  decision_analysis: (dashboard) =>
    JSON.stringify(
      {
        type: "decision_analyze_response",
        context: {
          critical_alerts: dashboard.criticalAlerts ?? 0,
          pending_approvals: dashboard.pendingApprovals ?? 0,
          graph_nodes: dashboard.graphNodesTotal ?? 0
        },
        committee: ["claude", "openai-gpt5", "openai-gpt45"],
        expected_output: {
          risk_level: 4,
          recommendation: "requires_approval",
          explanation: "human readable synthesis"
        }
      },
      null,
      2
    ),
  ad_drift: () =>
    JSON.stringify(
      {
        drift_type: "sensitive_group_change",
        object_dn: "CN=svc-backup,OU=Service Accounts,DC=corp,DC=local",
        severity: 5,
        auto_fixable: false,
        fix_action: "remove_from_sensitive_group"
      },
      null,
      2
    ),
  trust_profile: () =>
    JSON.stringify(
      {
        entity_id: "machine:dc-01",
        score_after: 41.2,
        state: "observation",
        restrictions: ["no_new_secrets", "limited_egress"]
      },
      null,
      2
    )
};

async function loadDashboard(): Promise<DashboardPayload> {
  const response = await fetch("/api/dashboard", { cache: "no-store" });
  if (!response.ok) {
    return {};
  }
  return response.json();
}

export function SchemaExplorer() {
  const [active, setActive] = useState<keyof typeof SCHEMA_TEMPLATES>("sentinel_evidence");
  const { data } = useQuery({
    queryKey: ["schema-dashboard"],
    queryFn: loadDashboard,
    refetchInterval: 10_000
  });

  const value = useMemo(() => SCHEMA_TEMPLATES[active](data ?? {}), [active, data]);

  return (
    <section className="grid gap-6 xl:grid-cols-[0.36fr_0.64fr]">
      <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
        <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
          Schema Explorer
        </h2>
        <p className="mt-2 text-sm text-muted">
          Contrats de lecture pour Sentinel, Decision, AD drift et trust profile.
        </p>

        <div className="mt-5 space-y-2">
          {Object.keys(SCHEMA_TEMPLATES).map((schemaId) => (
            <button
              key={schemaId}
              type="button"
              onClick={() => setActive(schemaId as keyof typeof SCHEMA_TEMPLATES)}
              className={`w-full rounded-2xl border px-4 py-3 text-left ${
                active === schemaId
                  ? "border-cyan-400/60 bg-cyan-400/10"
                  : "border-border/70 bg-background/35"
              }`}
            >
              <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                {schemaId.replaceAll("_", " ")}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-3xl border bg-panel/80 shadow-panel">
        <div className="border-b border-border/70 px-4 py-3">
          <div className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">
            {active.replaceAll("_", " ")}
          </div>
        </div>
        <div className="h-[34rem]">
          <Editor
            height="100%"
            defaultLanguage="json"
            language="json"
            value={value}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 13,
              wordWrap: "on",
              scrollBeyondLastLine: false
            }}
            theme="vs-dark"
          />
        </div>
      </div>
    </section>
  );
}
