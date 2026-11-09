/** Base URL for API calls. Server components prefer the internal (compose network) URL. */
export function apiBaseUrl(): string {
  if (typeof window === "undefined" && process.env.API_URL_INTERNAL) {
    return process.env.API_URL_INTERNAL;
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export type Health = {
  status: "ok" | "degraded";
  version: string;
  database: "ok" | "unavailable";
};

/** Returns null when the API can't be reached, so pages can show an error state. */
export async function getHealth(): Promise<Health | null> {
  try {
    const res = await fetch(`${apiBaseUrl()}/api/v1/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}
