export function serviceAuthHeaders(): Record<string, string> {
  const token = process.env.CORTEX_INTERNAL_API_TOKEN ?? "";
  return token ? { "x-cortex-internal-token": token } : {};
}
