import { useCallback, useEffect, useState } from "react";
import { API_BASE, fetchEvents } from "../services/api";
import { num, shortDate } from "../lib/format";
import type { Analysis, EventSort, EventsPage } from "../types/api";
import { hazardLabels } from "../lib/hazards";
import { EmptyView, ErrorView } from "./StateViews";

const PAGE_SIZE = 10;
export function EventsTable({ analysis }: { analysis: Analysis }) {
  const labels = hazardLabels(analysis.hazard);
  const columns: { key: EventSort | null; label: string; align?: string }[] = [
    { key: "start", label: "Start" }, { key: null, label: "End" },
    { key: "duration", label: "Days", align: "text-right" },
    { key: "peak", label: `Extreme (${labels.unit})`, align: "text-right" },
    { key: null, label: `Mean (${labels.unit})`, align: "text-right" },
    { key: "intensity", label: `Excess (${labels.unit}·days)`, align: "text-right" },
  ];
  const [year, setYear] = useState<number | null>(null);
  const [sort, setSort] = useState<EventSort>("start");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const [state, setState] = useState<{ status: "loading" } | { status: "error"; error: Error } | { status: "ok"; data: EventsPage }>({ status: "loading" });

  const years = analysis.result.annual.filter((a) => a.event_count > 0).map((a) => a.year);

  const load = useCallback(() => {
    let live = true;
    setState({ status: "loading" });
    fetchEvents(analysis.id, { year, sort, order, page, pageSize: PAGE_SIZE })
      .then((data) => live && setState({ status: "ok", data }))
      .catch((error: Error) => live && setState({ status: "error", error }));
    return () => { live = false; };
  }, [analysis.id, year, sort, order, page]);

  useEffect(() => load(), [load]);

  const toggleSort = (k: EventSort) => {
    if (k === sort) setOrder(order === "asc" ? "desc" : "asc");
    else {
      setSort(k);
      setOrder(k === "start" || (k === "peak" && analysis.hazard === "cold_wave") ? "asc" : "desc");
    }
    setPage(1);
  };

  const total = state.status === "ok" ? state.data.total : 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const maxDur = state.status === "ok" ? Math.max(1, ...state.data.items.map((e) => e.duration_days)) : 1;

  return (
    <section aria-labelledby="events-title" className="rounded-lg border border-line bg-surface p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="events-title" className="text-xl font-bold">{labels.events}</h2>
          <p className="text-sm text-muted">{analysis.events_total} detected. Select a column heading to sort.</p>
        </div>
        <label className="text-sm">
          <span className="mr-2 text-muted">Year</span>
          <select value={year ?? ""} onChange={(e) => { setYear(e.target.value ? Number(e.target.value) : null); setPage(1); }}
            className="rounded-md border border-line bg-surface px-2 py-1.5">
            <option value="">All years</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </label>
        <a
          href={`${API_BASE}/api/analyses/${analysis.id}/events.csv${year ? `?year=${year}` : ""}`}
          className="inline-flex items-center gap-2 rounded-md border border-line px-3 py-2 text-sm font-semibold text-ink transition hover:border-ember hover:bg-ember/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ember"
          aria-label={`Download ${year ? `${year} ` : "all "}${labels.name.toLowerCase()} events as CSV`}
        >
          <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" className="h-4 w-4" stroke="currentColor" strokeWidth="1.7">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 2.75v9m0 0 3.25-3.25M10 11.75 6.75 8.5M3.5 12.75v3A1.75 1.75 0 0 0 5.25 17.5h9.5a1.75 1.75 0 0 0 1.75-1.75v-3" />
          </svg>
          Download CSV
        </a>
      </div>

      <div className="mt-4">
        {state.status === "error" && <ErrorView error={state.error} onRetry={load} title="Events couldn't be loaded" />}
        {state.status === "ok" && state.data.total === 0 && (
          <EmptyView compact title={`No ${labels.name.toLowerCase()} events`}>
            {year ? `No events began in ${year}. Choose another year or all years.` : "No run of consecutive days met the threshold in this period."}
          </EmptyView>
        )}
        {(state.status === "loading" || (state.status === "ok" && state.data.total > 0)) && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-muted">
                  {columns.map((c) => (
                    <th key={c.label} scope="col" className={`py-2 pr-3 font-medium ${c.align ?? ""}`}
                      aria-sort={c.key && c.key === sort ? (order === "asc" ? "ascending" : "descending") : undefined}>
                      {c.key ? (
                        <button onClick={() => toggleSort(c.key as EventSort)} className="font-medium hover:text-ink">
                          {c.label}{c.key === sort ? (order === "asc" ? " ↑" : " ↓") : ""}
                        </button>
                      ) : c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {state.status === "loading"
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i} className="border-b border-line/60"><td colSpan={6} className="py-3"><div className="h-4 animate-pulse rounded bg-mist" /></td></tr>
                    ))
                  : state.data.items.map((e) => (
                      <tr key={e.start} className="border-b border-line/60">
                        <td className="py-2 pr-3">{shortDate(e.start)}</td>
                        <td className="py-2 pr-3">{shortDate(e.end)}</td>
                        <td className="py-2 pr-3 text-right">
                          <span className="inline-flex items-center gap-2">
                            <span aria-hidden className="h-2 rounded bg-ember" style={{ width: `${Math.max(6, (e.duration_days / maxDur) * 56)}px` }} />
                            {e.duration_days}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-right font-semibold">{num(e.extreme_value)}</td>
                        <td className="py-2 pr-3 text-right">{num(e.mean_value)}</td>
                        <td className="py-2 text-right">{num(e.cumulative_excess)}</td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {state.status === "ok" && state.data.total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="text-muted">Page {page} of {pages}</span>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-md border border-line px-3 py-1.5 disabled:opacity-40">Previous</button>
            <button disabled={page >= pages} onClick={() => setPage(page + 1)} className="rounded-md border border-line px-3 py-1.5 disabled:opacity-40">Next</button>
          </div>
        </div>
      )}
    </section>
  );
}
