import { heatColor } from "../lib/colors";
import { regionLabel, shortDate, num } from "../lib/format";
import { hazardLabels } from "../lib/hazards";
import type { Analysis } from "../types/api";

export function StripesHero({ data }: { data: Analysis }) {
  const { annual, summary } = data.result;
  const labels = hazardLabels(data.hazard);
  const days = (year: typeof annual[number]) => year.event_days ?? year.heatwave_days ?? 0;
  const max = Math.max(1, ...annual.filter((a) => a.complete).map(days));
  const p = data.params;
  const rule = data.hazard === "heatwave"
    ? `Daily maximum temperature above the ${p.percentile}th percentile`
    : data.hazard === "cold_wave"
      ? `Daily minimum temperature below the ${p.percentile}th percentile`
      : `Daily precipitation above the ${p.percentile}th percentile of wet days (at least 1 mm)`;
  return (
    <section aria-labelledby="hero-title">
      <p className="text-sm text-muted">
        {labels.eventDays} per year · {shortDate(p.start_date)} to {shortDate(p.end_date)}
        {data.cached && <span className="ml-2 rounded bg-mist px-2 py-0.5 text-xs">Cached result</span>}
      </p>
      <h1 id="hero-title" className="mt-1 text-4xl font-bold sm:text-5xl">{regionLabel(data.region)}</h1>
      <p className="mt-2 max-w-prose text-sm text-muted">
        {p.min_duration}+ consecutive day(s): {rule.toLowerCase()} ({num(summary.threshold_value)} {summary.unit === "C" ? "°C" : "mm"})
        {data.region.type === "bbox" ? ` (mean of ${data.region.sample_points} grid points)` : ""}.
      </p>
      <div role="img" aria-label={`${labels.eventDays} per year from ${annual[0]?.year} to ${annual.at(-1)?.year}, darker means more`}
        className="mt-5 flex h-36 gap-[2px] overflow-hidden rounded-lg border border-line sm:h-44">
        {annual.map((a, i) => (
          <div key={a.year} title={`${a.year}: ${days(a)} ${labels.eventDays.toLowerCase()}${a.complete ? "" : " (incomplete year)"}`}
            className={`stripe-enter flex-1 ${a.complete ? "" : "hatch"}`}
            style={{ animationDelay: `${i * 12}ms`, background: a.complete ? heatColor(days(a), max) : undefined }} />
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted">
        <span>{annual[0]?.year}</span>
        <span className="flex items-center gap-2">
          0 days
          <span aria-hidden className="h-2 w-24 rounded" style={{ background: `linear-gradient(90deg, ${heatColor(0, 1)}, ${heatColor(0.5, 1)}, ${heatColor(1, 1)})` }} />
          {max} days
          <span aria-hidden className="hatch ml-3 inline-block h-3 w-3 rounded-sm" /> incomplete year
        </span>
        <span>{annual.at(-1)?.year}</span>
      </div>
    </section>
  );
}
