import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { consoleInternalHeaders } from "@/lib/internal-fetch";
import { serviceAuthHeaders } from "@/lib/service-fetch";

type FeedEvent = { severity?: number; service?: string };
type Approval = { deadline_ts?: number; deadlineTs?: number };
type GraphNode = Record<string, unknown>;
type GraphOverview = { nodes?: GraphNode[] };
type ServiceHealth = { status?: string; latency?: number };
type AuthSummary = { active_sessions?: number; users_low_trust?: number };
type SyncSummary = { last_success?: string; delta_pending?: number };
type DecisionSurface = {
  degradedWarnings?: string[];
  maturityCounts?: Record<string, number>;
  executionModeCounts?: Record<string, number>;
};

function approvalDeadline(approval: Approval) {
  return approval.deadlineTs ?? approval.deadline_ts ?? 0;
}

function healthLatency(health: Record<string, ServiceHealth>, serviceName: string) {
  const latency = Number(health[serviceName]?.latency ?? 0);
  return Number.isFinite(latency) ? Math.round(latency) : 0;
}

function stringField(record: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function numberField(record: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function booleanField(record: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "boolean") {
      return value;
    }
  }
  return null;
}

function countGraphNodes(nodes: GraphNode[], predicate: (node: GraphNode) => boolean) {
  return nodes.filter(predicate).length;
}

function parsePrometheusCounterSum(metrics: string, metricName: string) {
  const pattern = new RegExp(`^${metricName}(?:\\{[^}]*\\})?\\s+([0-9eE+\\-.]+)$`, "gm");
  let total = 0;
  for (const match of metrics.matchAll(pattern)) {
    total += Number(match[1] ?? 0);
  }
  return Number.isFinite(total) ? Math.round(total) : 0;
}

async function safeFetchText(url: string, headers?: HeadersInit) {
  try {
    const response = await fetch(url, { cache: "no-store", headers });
    if (!response.ok) {
      return "";
    }
    return await response.text();
  } catch {
    return "";
  }
}

async function safeFetchJson<T>(url: string, fallback: T, headers?: HeadersInit) {
  try {
    const response = await fetch(url, { cache: "no-store", headers });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const [feedResp, healthResp, approvalsResp, graphResp, decisionResp, mcpMetrics, authSummary, syncSummary] =
      await Promise.all([
      fetch("http://cortex-obs-agent:8080/v1/feed", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-obs-agent:8080/v1/health", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-approval:8080/v1/approvals?status=pending", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-graph:8080/v1/graph/overview", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-console:3000/api/decision-surface", {
        cache: "no-store",
        headers: consoleInternalHeaders()
      }),
      safeFetchText("http://cortex-mcp-server:8080/metrics"),
      safeFetchJson<AuthSummary>("http://cortex-auth:8080/v1/sessions/summary", {}),
      safeFetchJson<SyncSummary>("http://cortex-sync:8080/v1/sync/summary", {})
    ]);

    const feed = (feedResp.ok ? await feedResp.json() : []) as FeedEvent[];
    const health = (healthResp.ok ? await healthResp.json() : {}) as Record<string, ServiceHealth>;
    const approvals = (approvalsResp.ok ? await approvalsResp.json() : []) as Approval[];
    const graph = (graphResp.ok ? await graphResp.json() : { nodes: [] }) as GraphOverview;
    const decisionSurface = (decisionResp.ok ? await decisionResp.json() : {}) as DecisionSurface;
    const now = Date.now() / 1000;

    const criticalAlerts = feed.filter((event) => (event.severity ?? 1) >= 4).length;
    const pendingApprovals = approvals.length;
    const approvalsPendingOldest = approvals.length
      ? Math.max(
          0,
          Math.round(
            approvals
              .map((approval) => ((approvalDeadline(approval) || now) - now) / 60)
              .reduce((smallest, current) => Math.min(smallest, current), Number.POSITIVE_INFINITY)
          )
        )
      : 0;
    const trustEngineLatencyP99 = healthLatency(health, "cortex-trust-engine");
    const extAuthzLatencyP99 = healthLatency(health, "cortex-envoy");
    const policyDecisionsPerSec = feed.filter((event) => event.service === "cortex-gateway").length;
    const graphNodes = graph.nodes ?? [];
    const activeSessionsCountFromGraph = countGraphNodes(graphNodes, (node) => {
      const type = stringField(node, "type", "entity_type").toLowerCase();
      return type === "session";
    });
    const activeSessionsCount = Number(authSummary.active_sessions ?? activeSessionsCountFromGraph);
    const usersWithLowTrust = countGraphNodes(graphNodes, (node) => {
      const type = stringField(node, "type", "entity_type").toLowerCase();
      const trustScore = numberField(node, "trust_score", "trustScore");
      return type === "user" && trustScore !== null && trustScore < 40;
    });
    const devicesNonCompliant = countGraphNodes(graphNodes, (node) => {
      const type = stringField(node, "type", "entity_type").toLowerCase();
      if (type !== "device" && type !== "machine") {
        return false;
      }
      const compliant = booleanField(node, "compliant", "is_compliant");
      if (compliant !== null) {
        return !compliant;
      }
      const status = stringField(node, "compliance_status", "complianceStatus", "state").toLowerCase();
      return status === "non_compliant" || status === "degraded";
    });
    const aiAgentsMonitored =
      countGraphNodes(graphNodes, (node) => {
        const type = stringField(node, "type", "entity_type").toLowerCase();
        return type === "agent" || type === "aiagent";
      }) || Object.keys(health).length;
    const mcpCallsObserved = parsePrometheusCounterSum(mcpMetrics, "cortex_mcp_calls_total");
    const authUsersLowTrust = Number(authSummary.users_low_trust ?? usersWithLowTrust);
    const adSyncLastSuccess = typeof syncSummary.last_success === "string" ? syncSummary.last_success : "";
    const adSyncDeltaPending = Number(syncSummary.delta_pending ?? 0);
    const degradedWarnings = [...(decisionSurface.degradedWarnings ?? [])];
    if (!mcpMetrics) {
      degradedWarnings.push("MCP metrics unavailable from console.");
    }
    if (!activeSessionsCount) {
      degradedWarnings.push("Active session inventory is not yet exposed by auth sessions.");
    }
    if (!trustEngineLatencyP99) {
      degradedWarnings.push("Trust engine latency is approximated from health probes only.");
    }
    if (!extAuthzLatencyP99) {
      degradedWarnings.push("ext_authz latency is approximated from Envoy readiness only.");
    }

    return NextResponse.json({
      criticalAlerts,
      pendingApprovals,
      sentinelBlocked: feed.filter((event) => (event.service ?? "").startsWith("cortex-sentinel")).length,
      activeSessionsCount,
      usersWithLowTrust: authUsersLowTrust,
      devicesNonCompliant,
      aiAgentsMonitored,
      agentTasksLast1h: feed.length,
      mcpCallsLast1h: mcpCallsObserved,
      approvalsPendingOldest,
      trustEngineLatencyP99,
      extAuthzLatencyP99,
      policyDecisionsPerSec,
      graphNodesTotal: graph.nodes?.length ?? 0,
      adSyncLastSuccess,
      adSyncDeltaPending,
      degradedWarnings,
      capabilityMaturitySummary: decisionSurface.maturityCounts ?? {},
      executionModeSummary: decisionSurface.executionModeCounts ?? {}
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "dashboard_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
