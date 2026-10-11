import type { Analysis, AnalysisRequest, CityResult, EventSort, EventsPage } from "../types/api";

export const API_BASE: string =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status: number, public code: string, public details?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120_000, signal?: AbortSignal): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort("timeout"), timeoutMs);
  signal?.addEventListener("abort", () => ctrl.abort("cancelled"));
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      signal: ctrl.signal,
    });
  } catch {
    if (ctrl.signal.aborted && ctrl.signal.reason === "cancelled") throw new ApiError("Request cancelled.", 0, "cancelled");
    if (ctrl.signal.aborted) throw new ApiError("The server took too long to respond.", 0, "client_timeout");
    throw new ApiError(`Can't reach the analysis server at ${API_BASE}. Check that the backend is running.`, 0, "network_error");
  } finally {
    clearTimeout(timer);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const e = body?.error;
    throw new ApiError(e?.message ?? `Request failed (HTTP ${res.status}).`, res.status, e?.code ?? "http_error", e?.details);
  }
  return body as T;
}

export const searchCities = (q: string, signal?: AbortSignal) =>
  request<{ results: CityResult[] }>(`/api/cities?q=${encodeURIComponent(q)}`, undefined, 15_000, signal).then((r) => r.results);

export const createAnalysis = (req: AnalysisRequest) =>
  request<Analysis>("/api/analyses", { method: "POST", body: JSON.stringify(req) });

export interface EventsQuery {
  year?: number | null;
  sort: EventSort;
  order: "asc" | "desc";
  page: number;
  pageSize: number;
}

export const fetchEvents = (analysisId: string, q: EventsQuery) => {
  const p = new URLSearchParams({ sort: q.sort, order: q.order, page: String(q.page), page_size: String(q.pageSize) });
  if (q.year) p.set("year", String(q.year));
  return request<EventsPage>(`/api/analyses/${analysisId}/events?${p}`, undefined, 20_000);
};
