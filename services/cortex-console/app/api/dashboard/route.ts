import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { consoleInternalHeaders } from "@/lib/internal-fetch";
import { serviceAuthHeaders } from "@/lib/service-fetch";

type FeedEvent = { severity?: number; service?: string };
type Approval = { deadlineTs?: number };
type GraphOverview = { nodes?: Array<unknown> };
type DecisionSurface = {
  degradedWarnings?: string[];
  maturityCounts?: Record<string, number>;
  executionModeCounts?: Record<string, number>;
};

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const [feedResp, healthResp, approvalsResp, graphResp, decisionResp] = await Promise.all([
      fetch("http://cortex-obs-agent:8080/v1/feed", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-obs-agent:8080/v1/health", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-approval:8080/v1/approvals?status=pending", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-graph:8080/v1/graph/overview", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-console:3000/api/decision-surface", {
        cache: "no-store",
        headers: consoleInternalHeaders()
      })
    ]);

    const feed = (feedResp.ok ? await feedResp.json() : []) as FeedEvent[];
    const health = (healthResp.ok ? await healthResp.json() : {}) as Record<string, { status?: string }>;
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
              .map((approval) => ((approval.deadlineTs ?? now) - now) / 60)
              .reduce((smallest, current) => Math.min(smallest, current), Number.POSITIVE_INFINITY)
          )
        )
      : 0;

    return NextResponse.json({
      criticalAlerts,
      pendingApprovals,
      sentinelBlocked: feed.filter((event) => event.service === "cortex-sentinel").length,
      activeSessionsCount: 0,
      usersWithLowTrust: 0,
      devicesNonCompliant: 0,
      aiAgentsMonitored: Object.keys(health).length,
      agentTasksLast1h: feed.length,
      mcpCallsLast1h: 0,
      approvalsPendingOldest,
      trustEngineLatencyP99: 0,
      extAuthzLatencyP99: 0,
      policyDecisionsPerSec: 0,
      graphNodesTotal: graph.nodes?.length ?? 0,
      adSyncLastSuccess: new Date().toISOString(),
      adSyncDeltaPending: 0,
      degradedWarnings: decisionSurface.degradedWarnings ?? [],
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
