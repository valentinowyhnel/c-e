import { NextResponse } from "next/server";
import { requireConsoleRead } from "@/lib/api-auth";
import { serviceAuthHeaders } from "@/lib/service-fetch";

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  const { searchParams } = new URL(request.url);
  const source = searchParams.get("source") ?? "";
  const target = searchParams.get("target") ?? "tier0";

  try {
    const response = await fetch(
      `http://bloodhound-ce:8080/api/v2/attack-paths?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`,
      { cache: "no-store", headers: serviceAuthHeaders() }
    );
    if (!response.ok) {
      throw new Error(`attack_path_status_${response.status}`);
    }

    return NextResponse.json(await response.json());
  } catch (error) {
    return NextResponse.json(
      {
        error: "attack_paths_unavailable",
        detail: error instanceof Error ? error.message : "unknown error"
      },
      { status: 503 }
    );
  }
}
