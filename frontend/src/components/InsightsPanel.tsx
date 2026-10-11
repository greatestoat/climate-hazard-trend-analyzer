import type { Analysis } from "../types/api";

const BAR = { warning: "bg-ember", info: "bg-tide", notice: "bg-amber" } as const;

export function InsightsPanel({ data }: { data: Analysis }) {
  return (
    <section aria-labelledby="insights-title" className="rounded-lg border border-line bg-surface p-5">
      <h2 id="insights-title" className="text-xl font-bold">What the data shows</h2>
      <p className="mb-4 text-sm text-muted">Generated from this analysis only.</p>
      <ul className="space-y-4">
        {data.result.insights.map((i) => (
          <li key={i.id} className="flex gap-3">
            <span aria-hidden className={`w-1 shrink-0 rounded ${BAR[i.severity]}`} />
            <div>
              <p className="font-semibold">{i.title}</p>
              <p className="text-sm text-muted">{i.text}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MethodPanel({ data }: { data: Analysis }) {
  const q = data.result.quality;
  const rows: [string, string][] = [
    ["Region representation", data.region.representation],
    ["Data source", q.source === "open-meteo" ? "Open-Meteo (fresh download)" : q.source === "cache" ? "MongoDB cache" : q.source === "stale_cache" ? "Stored data (API unavailable)" : "—"],
    ["Valid days", `${q.valid_days.toLocaleString()} of ${q.total_days.toLocaleString()} (${q.missing_pct}% missing)`],
    ["Gaps interpolated (≤ 2 days)", String(q.interpolated_days)],
    ["Outliers removed", String(q.outliers_removed)],
    ["Duplicate dates merged", String(q.duplicates_removed)],
    ["Invalid rows ignored", String(q.invalid_rows)],
  ];
  return (
    <section aria-labelledby="method-title" className="rounded-lg border border-line bg-surface p-5">
      <h2 id="method-title" className="text-xl font-bold">Method and data quality</h2>
      {data.warnings.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-md bg-amber/15 p-3 text-sm">{data.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}
      <dl className="mt-4 divide-y divide-line text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-4 py-2"><dt className="text-muted">{k}</dt><dd className="text-right font-medium">{v}</dd></div>
        ))}
      </dl>
    </section>
  );
}
