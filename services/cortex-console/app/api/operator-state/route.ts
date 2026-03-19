import { NextResponse } from "next/server";

import { requireConsoleAdmin, requireConsoleRead } from "@/lib/api-auth";
import { readOperatorState, writeOperatorState } from "@/lib/operator-state";

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  const { searchParams } = new URL(request.url);
  const scope = searchParams.get("scope") ?? "default";
  const payload = await readOperatorState(scope, {});
  return NextResponse.json(payload);
}

export async function PUT(request: Request) {
  const denied = requireConsoleAdmin(request);
  if (denied) return denied;
  const { searchParams } = new URL(request.url);
  const scope = searchParams.get("scope") ?? "default";
  const body = await request.json();
  await writeOperatorState(scope, body);
  return NextResponse.json({ ok: true, scope });
}
