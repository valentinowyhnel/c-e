import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { consoleInternalHeaders } from "@/lib/internal-fetch";
import { serviceAuthHeaders } from "@/lib/service-fetch";

async function safeFetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      return fallback;
    }
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

type ApprovalItem = {
  request_id?: string;
  plan_id?: string;
  requestor_id?: string;
  risk_level?: number;
  reasoning?: string;
  actions?: Array<Record<string, unknown>>;
  deadline_ts?: number;
  approvers_required?: number;
  approvals_received?: number;
  status?: string;
  correlation_id?: string;
  execution_mode?: string;
  capability_maturity?: string;
  degraded_mode?: boolean;
  risk_envelope?: Record<string, unknown>;
};

type HealthPayload = {
  status?: string;
  service?: string;
  operatorState?: { writable?: boolean };
  modelKeys?: {
    source?: string;
    writable?: boolean;
    configuredProviders?: string[];
  };
};

type GovernancePayload = {
  mcpReachable?: boolean;
  issues?: Array<{ level?: string; message?: string }>;
  summary?: {
    agentsCovered?: number;
    totalAgents?: number;
    readyTasks?: number;
    totalTasks?: number;
    verifiedModels?: number;
    totalModels?: number;
  };
  keyBackend?: { source?: string; writable?: boolean };
};

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  const [approvals, health, governance] = await Promise.all([
    fetch("http://cortex-approval:8080/v1/approvals?status=pending", {
      cache: "no-store",
      headers: serviceAuthHeaders()
    }).then(async (response) => (response.ok ? ((await response.json()) as ApprovalItem[]) : [])),
    safeFetchJson<HealthPayload>("http://cortex-console:3000/api/health", {}),
    fetch("http://cortex-console:3000/api/model-governance", {
      cache: "no-store",
      headers: consoleInternalHeaders()
    }).then(async (response) => (response.ok ? ((await response.json()) as GovernancePayload) : {}))
  ]);

  const degradedWarnings: string[] = [];
  if (!governance.mcpReachable) {
    degradedWarnings.push("MCP unreachable from console.");
  }
  if ((governance.summary?.readyTasks ?? 0) < (governance.summary?.totalTasks ?? 0)) {
    degradedWarnings.push("Some agent tasks are not backed by verified model assignments.");
  }
  if ((health.modelKeys?.configuredProviders?.length ?? 0) === 0) {
    degradedWarnings.push("No external model providers are configured.");
  }

  const maturityCounts = approvals.reduce<Record<string, number>>((acc, approval) => {
    const key = approval.capability_maturity || "unknown";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  const executionModeCounts = approvals.reduce<Record<string, number>>((acc, approval) => {
    const key = approval.execution_mode || "unknown";
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  return NextResponse.json({
    degradedWarnings,
    approvalCount: approvals.length,
    maturityCounts,
    executionModeCounts,
    approvals: approvals.map((approval) => ({
      requestId: String(approval.request_id ?? ""),
      planId: String(approval.plan_id ?? ""),
      requestorId: String(approval.requestor_id ?? ""),
      riskLevel: Number(approval.risk_level ?? 0),
      reasoning: String(approval.reasoning ?? ""),
      actions: Array.isArray(approval.actions) ? approval.actions : [],
      deadlineTs: Number(approval.deadline_ts ?? 0),
      approversRequired: Number(approval.approvers_required ?? 1),
      approvalsReceived: Number(approval.approvals_received ?? 0),
      status: String(approval.status ?? "pending"),
      correlationId: String(approval.correlation_id ?? ""),
      executionMode: String(approval.execution_mode ?? "prepare"),
      capabilityMaturity: String(approval.capability_maturity ?? "beta"),
      degradedMode: Boolean(approval.degraded_mode ?? false),
      riskEnvelope: approval.risk_envelope ?? {}
    })),
    governance: {
      mcpReachable: Boolean(governance.mcpReachable),
      keyBackend: governance.keyBackend ?? {},
      summary: governance.summary ?? {},
      issues: governance.issues ?? []
    },
    consoleHealth: health
  });
}
