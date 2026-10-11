import { dash, formatP, num, pct, shortDate, signed } from "../lib/format";
import { hazardLabels } from "../lib/hazards";
import type { AnalysisResult, Hazard } from "../types/api";

interface Tile { label: string; value: string; note: string }

export function buildTiles(r: AnalysisResult, hazard: Hazard): Tile[] {
  const s = r.summary, t = r.trend.event_days, c = r.changes.event_days;
  const labels = hazardLabels(hazard);
  const perYear = s.mean_event_days_per_year;
  const extreme = s.extreme_value === null ? dash : `${num(s.extreme_value)} ${labels.unit}`;
  return [
    { label: labels.events, value: num(s.total_events, 0), note: s.mean_events_per_year === null ? "No complete years" : `${num(s.mean_events_per_year)} per year on average` },
    { label: labels.eventDays, value: num(s.total_event_days, 0), note: perYear === null ? "No complete years" : `${num(perYear)} per year on average` },
    { label: "Average duration", value: s.mean_duration_days === null ? dash : `${num(s.mean_duration_days)} days`, note: s.longest_event ? `Longest: ${s.longest_event.duration_days} days from ${shortDate(s.longest_event.start)}` : "No events detected" },
    { label: labels.extreme, value: extreme, note: s.extreme_date ? `During an event, ${shortDate(s.extreme_date)}` : "No events detected" },
    { label: "OLS slope", value: t.available ? `${signed(t.slope_per_decade, 2)} days/decade` : dash, note: t.available ? `Exploratory · R² ${t.r_squared}, nominal p ${formatP(t.p_value)}` : t.reason ?? "Unavailable" },
    { label: "Late vs early period", value: c.valid ? pct(c.pct_change) : dash, note: c.valid ? `${c.early_period?.join("–")} vs ${c.late_period?.join("–")}` : c.reason ?? "Unavailable" },
  ];
}

export function SummaryCards({ result, hazard }: { result: AnalysisResult; hazard: Hazard }) {
  return (
    <section aria-label="Summary statistics" className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 xl:grid-cols-3">
      {buildTiles(result, hazard).map((t) => (
        <div key={t.label} className="bg-surface p-5">
          <p className="text-sm text-muted">{t.label}</p>
          <p className="mt-2 text-2xl font-bold">{t.value}</p>
          <p className="mt-1 text-xs text-muted">{t.note}</p>
        </div>
      ))}
    </section>
  );
}
