import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

type GraphNode = {
  id: string;
  type?: string;
  displayName?: string;
};

type GraphEdge = {
  source: string;
  target: string;
  type: string;
};

type GraphPayload = {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
};

type HealthPayload = Record<
  string,
  {
    status?: "healthy" | "degraded" | "unreachable";
    latency?: number;
  }
>;

type FeedEvent = {
  id?: string;
  service?: string;
  severity?: number;
  title?: string;
  explanation?: string;
};

type DeepSearchRecord = {
  id: string;
  label: string;
  type: string;
  category: "machine" | "resource" | "identity" | "agent" | "node";
  status: "healthy" | "degraded" | "unreachable" | "unknown";
  relationCount: number;
  attackPathCount: number;
  alerts: number;
  privilegeScore: number;
  resourcePressure: number;
  blastRadiusScore: number;
  driftScore: number;
  kerberosDelegationRisk: number;
  sensitiveGroupAffinity: number;
  tierZeroExposure: boolean;
  focusAreas: string[];
  riskBand: "low" | "medium" | "high" | "critical";
  healthLatency: number | null;
  searchText: string;
};

const TYPE_CATEGORY: Record<string, DeepSearchRecord["category"]> = {
  User: "identity",
  Group: "identity",
  Device: "machine",
  Service: "machine",
  Resource: "resource",
  Agent: "agent",
  AIAgent: "agent"
};

const TYPE_BASE_SCORE: Record<string, number> = {
  User: 36,
  Group: 58,
  Device: 32,
  Service: 54,
  Resource: 48,
  Agent: 68,
  AIAgent: 72
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

async function loadTierZeroAssets(): Promise<string[]> {
  try {
    const response = await fetch("http://bloodhound-ce:8080/api/v2/domains/default/tier-zero", {
      cache: "no-store"
    });
    if (!response.ok) {
      return [];
    }
    const payload = (await response.json()) as { data?: Array<{ objectid?: string }> };
    return (payload.data ?? []).map((item) => item.objectid ?? "").filter(Boolean);
  } catch {
    return [];
  }
}

function inferStatus(node: GraphNode, health: HealthPayload) {
  const key = Object.keys(health).find((name) =>
    [node.id, node.displayName ?? ""].some((value) =>
      value.toLowerCase().includes(name.replace("cortex-", "").toLowerCase())
    )
  );

  if (!key) {
    return { status: "unknown" as const, latency: null };
  }

  return {
    status: (health[key]?.status ?? "unknown") as
      | "healthy"
      | "degraded"
      | "unreachable"
      | "unknown",
    latency: health[key]?.latency ?? null
  };
}

function deriveRecords(
  graph: GraphPayload,
  health: HealthPayload,
  feed: FeedEvent[],
  tierZeroAssets: string[]
) {
  const nodes = graph.nodes ?? [];
  const edges = graph.edges ?? [];

  return nodes.map((node) => {
    const relationCount = edges.filter(
      (edge) => edge.source === node.id || edge.target === node.id
    ).length;
    const attackPathCount = edges.filter(
      (edge) =>
        edge.type === "attack_path" && (edge.source === node.id || edge.target === node.id)
    ).length;
    const linkedAlerts = feed.filter((event) => {
      const marker = `${event.service ?? ""} ${event.title ?? ""}`.toLowerCase();
      const target = `${node.id} ${node.displayName ?? ""}`.toLowerCase();
      return target && marker && target.includes(marker.split(" ")[0]) && (event.severity ?? 0) >= 3;
    }).length;

    const { status, latency } = inferStatus(node, health);
    const descriptor = `${node.id} ${node.displayName ?? ""}`.toLowerCase();
    const baseScore = TYPE_BASE_SCORE[node.type ?? ""] ?? 28;
    const tierZeroExposure =
      /tier0|domain admins|enterprise admins|domain controllers|break_glass|schema admins/i.test(
        descriptor
      ) ||
      tierZeroAssets.some((asset) => asset.toLowerCase() === node.id.toLowerCase()) ||
      attackPathCount > 0;
    const kerberosDelegationRisk = clamp(
      (/spn|svc|service|delegate|delegation|rbcd|kerberos/i.test(descriptor) ? 35 : 0) +
        (/svc|service/i.test(descriptor) ? 20 : 0) +
        attackPathCount * 14,
      0,
      100
    );
    const sensitiveGroupAffinity = clamp(
      (/domain admins|enterprise admins|schema admins|backup operators|account operators/i.test(
        descriptor
      )
        ? 70
        : 0) +
        relationCount * 2,
      0,
      100
    );
    const driftScore = clamp(
      (/drift|orphan|stale|gpo|deleted|recycle/i.test(descriptor) ? 50 : 0) +
        linkedAlerts * 8 +
        (status === "degraded" ? 10 : 0),
      0,
      100
    );
    const blastRadiusScore = clamp(
      relationCount * 5 +
        attackPathCount * 18 +
        linkedAlerts * 8 +
        (TYPE_CATEGORY[node.type ?? ""] === "resource" ? 8 : 0) +
        (TYPE_CATEGORY[node.type ?? ""] === "agent" ? 12 : 0),
      0,
      100
    );
    const privilegeScore = clamp(
      baseScore +
        attackPathCount * 20 +
        relationCount * 1.8 +
        linkedAlerts * 9 +
        (status === "degraded" ? 10 : 0) +
        (status === "unreachable" ? 15 : 0) +
        (/admin|tier0|domain/i.test(descriptor) ? 22 : 0) +
        (tierZeroExposure ? 12 : 0) +
        Math.round(sensitiveGroupAffinity / 8),
      0,
      100
    );
    const resourcePressure = clamp(relationCount * 4 + linkedAlerts * 10, 0, 100);
    const focusAreas = [
      ...(tierZeroExposure ? ["tier0"] : []),
      ...(attackPathCount > 0 ? ["attack_path"] : []),
      ...(blastRadiusScore >= 60 ? ["blast_radius"] : []),
      ...(driftScore >= 45 ? ["ad_drift"] : []),
      ...(kerberosDelegationRisk >= 45 ? ["kerberos"] : []),
      ...(sensitiveGroupAffinity >= 55 ? ["sensitive_group"] : [])
    ];

    let riskBand: DeepSearchRecord["riskBand"] = "low";
    if (privilegeScore >= 80) {
      riskBand = "critical";
    } else if (privilegeScore >= 60) {
      riskBand = "high";
    } else if (privilegeScore >= 35) {
      riskBand = "medium";
    }

    return {
      id: node.id,
      label: node.displayName ?? node.id,
      type: node.type ?? "Unknown",
      category: TYPE_CATEGORY[node.type ?? ""] ?? "node",
      status,
      relationCount,
      attackPathCount,
      alerts: linkedAlerts,
      privilegeScore,
      resourcePressure,
      blastRadiusScore,
      driftScore,
      kerberosDelegationRisk,
      sensitiveGroupAffinity,
      tierZeroExposure,
      focusAreas,
      riskBand,
      healthLatency: latency,
      searchText: [
        node.id,
        node.displayName ?? "",
        node.type ?? "",
        TYPE_CATEGORY[node.type ?? ""] ?? "node",
        status,
        ...focusAreas,
        tierZeroExposure ? "tier0" : "",
        kerberosDelegationRisk ? "kerberos delegation spn" : "",
        driftScore ? "drift gpo stale deleted orphan" : "",
        sensitiveGroupAffinity ? "domain admins enterprise admins schema admins" : ""
      ]
        .join(" ")
        .toLowerCase()
    } satisfies DeepSearchRecord;
  });
}

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const [graphResp, healthResp, feedResp] = await Promise.all([
      fetch("http://cortex-graph:8080/v1/graph/overview", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-obs-agent:8080/v1/health", { cache: "no-store", headers: serviceAuthHeaders() }),
      fetch("http://cortex-obs-agent:8080/v1/feed", { cache: "no-store", headers: serviceAuthHeaders() })
    ]);

    const graph = (graphResp.ok ? await graphResp.json() : { nodes: [], edges: [] }) as GraphPayload;
    const health = (healthResp.ok ? await healthResp.json() : {}) as HealthPayload;
    const feed = (feedResp.ok ? await feedResp.json() : []) as FeedEvent[];
    const tierZeroAssets = await loadTierZeroAssets();
    const records = deriveRecords(graph, health, feed, tierZeroAssets);

    return NextResponse.json({
      generatedAt: new Date().toISOString(),
      total: records.length,
      tierZeroAssets,
      records
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "deep_search_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
