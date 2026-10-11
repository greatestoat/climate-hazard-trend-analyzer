import { dash, formatP, num, pct, shortDate, signed } from "../lib/format";
import { hazardLabels } from "../lib/hazards";
import type { AnalysisResult, Hazard } from "../types/api";

interface Tile { label: string; value: string; note: string }

export function buildTiles(r: AnalysisResult, hazard: Hazard = "heatwave"): Tile[] {
  const s = r.summary;
  const t = r.trend.event_days ?? r.trend.heatwave_days;
  const mk = r.mann_kendall?.event_days;
  const c = r.changes.event_days ?? r.changes.heatwave_days;
  const labels = hazardLabels(hazard);
  const perYear = s.mean_event_days_per_year ?? s.mean_heatwave_days_per_year;
  const extremeValue = s.extreme_value ?? s.peak_temp_c;
  const extremeDate = s.extreme_date ?? s.peak_date;
  const extreme = extremeValue == null ? dash : `${num(extremeValue)} ${labels.unit}`;
  const eventDays = s.total_event_days ?? s.total_heatwave_days ?? 0;
  return [
    { label: labels.events, value: num(s.total_events, 0), note: s.mean_events_per_year === null ? "No complete years" : `${num(s.mean_events_per_year)} per year on average` },
    { label: labels.eventDays, value: num(eventDays, 0), note: perYear == null ? "No complete years" : `${num(perYear)} per year on average` },
    { label: "Average duration", value: s.mean_duration_days === null ? dash : `${num(s.mean_duration_days)} days`, note: s.longest_event ? `Longest: ${s.longest_event.duration_days} days from ${shortDate(s.longest_event.start)}` : "No events detected" },
    { label: labels.extreme, value: extreme, note: extremeDate ? `During an event, ${shortDate(extremeDate)}` : "No events detected" },
    { label: "OLS slope", value: t?.available ? `${signed(t.slope_per_decade, 2)} days/decade` : dash, note: t?.available ? `Exploratory; R2 ${t.r_squared}, nominal p ${formatP(t.p_value)}` : t?.reason ?? "Unavailable" },
    { label: "Mann-Kendall", value: mk?.available ? `tau ${signed(mk.tau, 3)}` : dash, note: mk?.available ? `Exploratory; nominal p ${formatP(mk.p_value)}` : mk?.reason ?? "Unavailable" },
    { label: "Late vs early period", value: c?.valid ? pct(c.pct_change) : dash, note: c?.valid ? `${c.early_period?.join("-")} vs ${c.late_period?.join("-")}` : c?.reason ?? "Unavailable" },
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
