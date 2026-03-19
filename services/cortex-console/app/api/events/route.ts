import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

type AuditEvent = {
  event_id?: string;
  timestamp?: number;
  event_type?: string;
  reason?: string;
  decision?: string;
};

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const response = await fetch("http://cortex-audit:8080/v1/events?limit=30", {
      cache: "no-store",
      headers: serviceAuthHeaders()
    });
    if (!response.ok) {
      throw new Error(`audit status ${response.status}`);
    }

    const payload = (await response.json()) as AuditEvent[];
    const items = payload.map((event) => ({
      id: String(event.event_id ?? crypto.randomUUID()),
      level:
        event.decision === "deny"
          ? "critical"
          : event.decision === "monitor"
            ? "warning"
            : "info",
      title: String(event.event_type ?? "audit.event"),
      timestamp: new Date((event.timestamp ?? Date.now() / 1000) * 1000).toISOString(),
      detail: String(event.reason ?? "")
    }));
    return NextResponse.json(items);
  } catch (error) {
    return NextResponse.json(
      {
        error: "events_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
