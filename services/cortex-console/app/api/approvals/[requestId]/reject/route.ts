import { NextRequest, NextResponse } from "next/server";
import { requireConsoleAdmin } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

export async function POST(
  request: NextRequest,
  { params }: { params: { requestId: string } }
) {
  const denied = requireConsoleAdmin(request);
  if (denied) return denied;
  const body = await request.text();

  try {
    const response = await fetch(
      `http://cortex-approval:8080/v1/approvals/${params.requestId}/reject`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...serviceAuthHeaders() },
        body
      }
    );

    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "approval_action_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
