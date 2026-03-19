import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const ROOT = process.env.CORTEX_CONSOLE_STATE_PATH ?? "/var/lib/cortex-console";

function safeScope(scope: string) {
  return scope.replace(/[^a-zA-Z0-9_-]/g, "_");
}

async function ensureRoot() {
  await mkdir(ROOT, { recursive: true });
}

function stateFile(scope: string) {
  return path.join(ROOT, `${safeScope(scope)}.json`);
}

export async function readOperatorState<T>(scope: string, fallback: T): Promise<T> {
  try {
    await ensureRoot();
    const raw = await readFile(stateFile(scope), "utf8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function writeOperatorState(scope: string, payload: unknown) {
  await ensureRoot();
  await writeFile(stateFile(scope), JSON.stringify(payload, null, 2), "utf8");
}

export async function operatorStateHealth() {
  try {
    await ensureRoot();
    return { writable: true, path: ROOT };
  } catch (error) {
    return {
      writable: false,
      path: ROOT,
      error: error instanceof Error ? error.message : "unknown error"
    };
  }
}
