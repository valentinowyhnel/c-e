import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  try {
    const response = await fetch("http://cortex-graph:8080/v1/graph/overview", {
      cache: "no-store",
      headers: serviceAuthHeaders()
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: "graph_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
