export function consoleInternalHeaders(): Record<string, string> {
  const token = process.env.CORTEX_CONSOLE_INTERNAL_TOKEN ?? "";
  if (!token) {
    return {};
  }
  return { "x-cortex-internal-token": token };
}
