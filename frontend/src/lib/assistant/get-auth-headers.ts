/**
 * Returns headers for the streaming fetch request.
 * Auth is handled server-side via Databricks forwarded headers.
 * No browser-managed tokens are needed for same-origin requests.
 */
export function getAuthHeaders(): Record<string, string> {
  return {
    'Content-Type': 'application/json',
  }
}
