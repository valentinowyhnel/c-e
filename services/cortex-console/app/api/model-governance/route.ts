import { NextResponse } from "next/server";

import {
  buildGovernanceView,
  readGovernanceState,
  writeGovernanceState,
  type ProviderId
} from "@/lib/model-governance";
import { requireConsoleAdmin, requireConsoleRead } from "@/lib/api-auth";
import { writeModelKeys } from "@/lib/vault-model-keys";

type IncomingPayload = {
  keys?: Partial<Record<ProviderId, string>>;
  assignments?: Record<string, Record<string, string>>;
};

function sanitizeKeys(incoming?: Partial<Record<ProviderId, string>>) {
  if (!incoming) {
    return {};
  }

  const merged: Partial<Record<ProviderId, string>> = {};
  for (const [provider, value] of Object.entries(incoming)) {
    if (typeof value === "string" && value.trim()) {
      merged[provider as ProviderId] = value.trim();
    }
  }
  return merged;
}

export async function GET(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  const state = await readGovernanceState();
  const view = await buildGovernanceView(state);
  return NextResponse.json(view);
}

export async function PUT(request: Request) {
  const denied = requireConsoleAdmin(request);
  if (denied) return denied;
  const current = await readGovernanceState();
  const body = (await request.json()) as IncomingPayload;
  const keys = sanitizeKeys(body.keys);
  if (Object.keys(keys).length) {
    await writeModelKeys(keys);
  }
  const next = await writeGovernanceState({
    assignments: body.assignments ?? current.assignments
  });
  const view = await buildGovernanceView(next);
  return NextResponse.json(view);
}

export async function POST(request: Request) {
  const denied = requireConsoleRead(request);
  if (denied) return denied;
  const current = await readGovernanceState();
  const body = (await request.json()) as IncomingPayload;
  const transient = { assignments: body.assignments ?? current.assignments, updatedAt: current.updatedAt };
  const view = await buildGovernanceView(transient);
  return NextResponse.json(view);
}
