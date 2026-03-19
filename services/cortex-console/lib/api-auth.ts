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

function trustSameOriginBrowserSession() {
  const raw = (process.env.CORTEX_CONSOLE_TRUST_SAME_ORIGIN ?? "").trim().toLowerCase();
  if (raw === "1" || raw === "true" || raw === "yes") {
    return true;
  }
  if (raw === "0" || raw === "false" || raw === "no") {
    return false;
  }
  return process.env.NODE_ENV !== "production";
}

function hostFromUrl(value: string | null) {
  if (!value) {
    return "";
  }
  try {
    return new URL(value).host.trim().toLowerCase();
  } catch {
    return value.trim().toLowerCase();
  }
}

function requestHost(request: Request) {
  return (
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    hostFromUrl(request.url)
  )
    .trim()
    .toLowerCase();
}

function isTrustedSameOriginBrowserRequest(request: Request) {
  if (!trustSameOriginBrowserSession()) {
    return false;
  }

  const secFetchSite = (request.headers.get("sec-fetch-site") ?? "").trim().toLowerCase();
  if (secFetchSite && secFetchSite !== "same-origin") {
    return false;
  }

  const expectedHost = requestHost(request);
  if (!expectedHost) {
    return false;
  }

  const originHost = hostFromUrl(request.headers.get("origin"));
  if (originHost && originHost === expectedHost) {
    return true;
  }

  const refererHost = hostFromUrl(request.headers.get("referer"));
  return Boolean(refererHost) && refererHost === expectedHost;
}

export function requireConsoleRead(request: Request): NextResponse | null {
  if (hasInternalToken(request) || isTrustedSameOriginBrowserRequest(request)) {
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
  if (hasInternalToken(request) || isTrustedSameOriginBrowserRequest(request)) {
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
