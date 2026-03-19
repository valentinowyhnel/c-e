import { NextResponse } from "next/server";

function scopesFromRequest(request: Request) {
  return (request.headers.get("x-cortex-scopes") ?? "")
    .split(",")
    .map((scope) => scope.trim())
    .filter(Boolean);
}

function hasInternalToken(request: Request) {
  const expected = process.env.CORTEX_CONSOLE_INTERNAL_TOKEN ?? "";
  if (!expected) {
    return false;
  }
  return request.headers.get("x-cortex-internal-token") === expected;
}

function hasUserIdentity(request: Request) {
  return Boolean((request.headers.get("x-cortex-user-id") ?? "").trim());
}

export function requireConsoleRead(request: Request): NextResponse | null {
  if (hasInternalToken(request)) {
    return null;
  }
  const scopes = scopesFromRequest(request);
  if (hasUserIdentity(request) && (scopes.includes("read:console") || scopes.includes("admin:write"))) {
    return null;
  }
  return NextResponse.json(
    { error: "forbidden", detail: "read:console or admin:write required" },
    { status: 403 }
  );
}

export function requireConsoleAdmin(request: Request): NextResponse | null {
  if (hasInternalToken(request)) {
    return null;
  }
  const scopes = scopesFromRequest(request);
  if (hasUserIdentity(request) && scopes.includes("admin:write")) {
    return null;
  }
  return NextResponse.json(
    { error: "forbidden", detail: "admin:write required" },
    { status: 403 }
  );
}
