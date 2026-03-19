import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";

import type { ProviderId } from "@/lib/model-governance";

const VAULT_ADDR = process.env.CORTEX_VAULT_ADDR ?? process.env.VAULT_ADDR ?? "";
const VAULT_TOKEN = process.env.CORTEX_VAULT_TOKEN ?? process.env.VAULT_TOKEN ?? "";
const SECRET_PATH = process.env.CORTEX_MODEL_KEYS_SECRET_PATH ?? "secret/data/cortex/model-keys";
const SECRET_FILE = process.env.CORTEX_MODEL_KEYS_FILE ?? "/vault/secrets/model-keys";

export type ModelKeys = Partial<Record<ProviderId, string>>;

function normalizePath(path: string) {
  return path.replace(/^\/v1\//, "");
}

function vaultDataUrl() {
  return `${VAULT_ADDR.replace(/\/$/, "")}/v1/${normalizePath(SECRET_PATH)}`;
}

async function readInjectedSecretFile(): Promise<ModelKeys> {
  if (!existsSync(SECRET_FILE)) {
    return {};
  }

  const raw = await readFile(SECRET_FILE, "utf8");
  const keys: ModelKeys = {};
  for (const line of raw.split(/\r?\n/)) {
    const clean = line.trim();
    if (!clean || clean.startsWith("#") || !clean.includes("=")) {
      continue;
    }
    const [name, ...rest] = clean.split("=");
    const value = rest.join("=").trim().replace(/^"(.*)"$/, "$1");
    if (name === "ANTHROPIC_API_KEY") {
      keys.anthropic = value;
    }
    if (name === "OPENAI_API_KEY") {
      keys.openai = value;
    }
    if (name === "VLLM_API_KEY") {
      keys.vllm_local = value;
    }
  }
  return keys;
}

async function readVaultHttp(): Promise<ModelKeys> {
  if (!VAULT_ADDR || !VAULT_TOKEN) {
    return {};
  }

  const response = await fetch(vaultDataUrl(), {
    cache: "no-store",
    headers: { "X-Vault-Token": VAULT_TOKEN }
  });

  if (!response.ok) {
    throw new Error(`Vault read failed: ${response.status}`);
  }

  const payload = (await response.json()) as { data?: { data?: Record<string, string> } };
  const data = payload.data?.data ?? {};
  return {
    anthropic: data.ANTHROPIC_API_KEY ?? "",
    openai: data.OPENAI_API_KEY ?? "",
    vllm_local: data.VLLM_API_KEY ?? ""
  };
}

export async function readModelKeys(): Promise<{ keys: ModelKeys; source: "vault_http" | "vault_file" | "none"; writable: boolean }> {
  if (VAULT_ADDR && VAULT_TOKEN) {
    const keys = await readVaultHttp();
    return { keys, source: "vault_http", writable: true };
  }
  if (existsSync(SECRET_FILE)) {
    const keys = await readInjectedSecretFile();
    return { keys, source: "vault_file", writable: false };
  }
  return { keys: {}, source: "none", writable: false };
}

export async function writeModelKeys(keys: ModelKeys) {
  if (!VAULT_ADDR || !VAULT_TOKEN) {
    throw new Error("Vault write unavailable: missing CORTEX_VAULT_ADDR or CORTEX_VAULT_TOKEN");
  }

  const response = await fetch(vaultDataUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Vault-Token": VAULT_TOKEN
    },
    body: JSON.stringify({
      data: {
        ANTHROPIC_API_KEY: keys.anthropic ?? "",
        OPENAI_API_KEY: keys.openai ?? "",
        VLLM_API_KEY: keys.vllm_local ?? ""
      }
    })
  });

  if (!response.ok) {
    throw new Error(`Vault write failed: ${response.status}`);
  }
}

export async function modelKeysHealth() {
  try {
    const state = await readModelKeys();
    return {
      source: state.source,
      writable: state.writable,
      configuredProviders: Object.entries(state.keys)
        .filter(([, value]) => Boolean(value))
        .map(([provider]) => provider)
    };
  } catch (error) {
    return {
      source: "error",
      writable: false,
      error: error instanceof Error ? error.message : "unknown error",
      configuredProviders: []
    };
  }
}
