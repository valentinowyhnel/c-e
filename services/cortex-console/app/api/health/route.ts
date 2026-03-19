import { NextResponse } from "next/server";
import { operatorStateHealth } from "@/lib/operator-state";
import { modelKeysHealth } from "@/lib/vault-model-keys";

export async function GET() {
  const operatorState = await operatorStateHealth();
  const modelKeys = await modelKeysHealth();
  return NextResponse.json({ status: "ok", service: "cortex-console", operatorState, modelKeys });
}
