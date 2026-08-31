// Real fetch path - only actually called once VITE_USE_MOCKS=false and a
// real backend exists to point VITE_API_BASE_URL at. Every resource module
// (see api/dashboard.ts) calls through here instead of its own fetch(), so
// auth headers / error handling change in one place.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_BASE_URL) {
    throw new Error(
      `No API base URL configured (VITE_API_BASE_URL) - can't fetch "${path}" for real. ` +
        "Either set VITE_USE_MOCKS=true to keep using mock data, or configure VITE_API_BASE_URL.",
    )
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`API request to ${path} failed: ${response.status} ${response.statusText}`)
  }

  return response.json() as Promise<T>
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
}
