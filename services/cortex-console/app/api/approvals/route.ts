import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

function normalizeApproval(payload: Record<string, unknown>) {
  return {
    requestId: String(payload.request_id ?? ""),
    planId: String(payload.plan_id ?? ""),
    requestorId: String(payload.requestor_id ?? ""),
    riskLevel: Number(payload.risk_level ?? 4),
    reasoning: String(payload.reasoning ?? ""),
    actions: Array.isArray(payload.actions) ? payload.actions : [],
    deadlineTs: Number(payload.deadline_ts ?? 0),
    approversRequired: Number(payload.approvers_required ?? 1),
    approvalsReceived: Number(payload.approvals_received ?? 0),
    status: String(payload.status ?? "pending"),
    correlationId: String(payload.correlation_id ?? ""),
    executionMode: String(payload.execution_mode ?? "prepare"),
    capabilityMaturity: String(payload.capability_maturity ?? "beta"),
    degradedMode: Boolean(payload.degraded_mode ?? false),
    riskEnvelope:
      payload.risk_envelope && typeof payload.risk_envelope === "object"
        ? (payload.risk_envelope as Record<string, unknown>)
        : {}
  };
}

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  const { searchParams } = new URL(request.url);
  const status = searchParams.get("status") ?? "pending";

  try {
    const response = await fetch(`http://cortex-approval:8080/v1/approvals?status=${status}`, {
      cache: "no-store",
      headers: serviceAuthHeaders()
    });
    if (!response.ok) {
      throw new Error(`approval status ${response.status}`);
    }

    const payload = (await response.json()) as Array<Record<string, unknown>>;
    return NextResponse.json(payload.map(normalizeApproval));
  } catch (error) {
    return NextResponse.json(
      {
        error: "approvals_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
