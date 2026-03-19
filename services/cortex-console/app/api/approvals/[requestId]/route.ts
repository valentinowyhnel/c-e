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
    status: String(payload.status ?? "pending")
  };
}

export async function GET(
  request: Request,
  { params }: { params: { requestId: string } }
) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const response = await fetch(`http://cortex-approval:8080/v1/approvals/${params.requestId}`, {
      cache: "no-store",
      headers: serviceAuthHeaders()
    });
    return NextResponse.json(normalizeApproval(await response.json()), { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "approval_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
