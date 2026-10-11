import type { ReactNode } from "react";
import { ApiError } from "../services/api";

export function LoadingView({ label = "Analysing climate history" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-6">
      <div className="h-40 overflow-hidden rounded-lg border border-line bg-surface p-4">
        <div className="flex h-full gap-[2px]">
          {Array.from({ length: 36 }).map((_, i) => (
            <div key={i} className="flex-1 animate-pulse rounded-sm bg-mist" style={{ animationDelay: `${i * 40}ms` }} />
          ))}
        </div>
      </div>
      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="font-display text-xl font-bold">{label}…</p>
        <p className="mt-2 max-w-prose text-sm text-muted">
          The first analysis of a region downloads its full daily temperature history from Open-Meteo and can take up to a minute.
          Repeat runs for the same region and dates are served from the cache.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="h-72 animate-pulse rounded-lg border border-line bg-surface" />
        ))}
      </div>
    </div>
  );
}

export function EmptyView({ title, children, compact = false }: { title: string; children?: ReactNode; compact?: boolean }) {
  return (
    <div className={`rounded-lg border border-dashed border-line bg-surface text-center ${compact ? "p-6" : "p-12"}`}>
      <p className="font-display text-xl font-bold">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-prose text-sm text-muted">{children}</div>}
    </div>
  );
}

const HINTS: Record<string, string> = {
  network_error: "Start the backend (uvicorn app.main:app --reload) and confirm VITE_API_BASE_URL points to it.",
  client_timeout: "The request took too long. Try again, or choose a smaller date range or box.",
  upstream_timeout: "Open-Meteo did not respond in time. Retrying usually works.",
  upstream_error: "Open-Meteo could not be reached or rejected the request. Retrying in a moment usually works.",
  rate_limited: "You've sent too many requests. Wait a minute, then retry.",
  database_unavailable: "MongoDB isn't reachable. Start it and retry.",
  insufficient_data: "Try a longer period or a different location.",
  validation_error: "Adjust the highlighted inputs and run the analysis again.",
};

export function ErrorView({ error, onRetry, title = "The analysis couldn't be completed" }: { error: ApiError | Error; onRetry?: () => void; title?: string }) {
  const code = error instanceof ApiError ? error.code : "unknown";
  return (
    <div role="alert" className="rounded-lg border border-ember/40 bg-surface p-6">
      <p className="font-display text-xl font-bold text-ember">{title}</p>
      <p className="mt-2 text-sm">{error.message}</p>
      {HINTS[code] && <p className="mt-1 text-sm text-muted">{HINTS[code]}</p>}
      {onRetry && (
        <button onClick={onRetry} className="mt-4 rounded-md bg-ink px-4 py-2 text-sm font-semibold text-paper hover:bg-ink-soft">
          Retry
        </button>
      )}
    </div>
  );
}
