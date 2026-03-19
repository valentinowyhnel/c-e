import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const response = await fetch("http://cortex-obs-agent:8080/v1/health", {
      cache: "no-store",
      headers: serviceAuthHeaders()
    });
    if (!response.ok) {
      throw new Error(`obs-agent health status ${response.status}`);
    }
    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json(
      {
        error: "obs_health_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
