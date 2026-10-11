import { heatColor } from "../lib/colors";
import { regionLabel, shortDate, temp } from "../lib/format";
import type { Analysis } from "../types/api";

export function StripesHero({ data }: { data: Analysis }) {
  const { annual, summary } = data.result;
  const max = Math.max(1, ...annual.filter((a) => a.complete).map((a) => a.heatwave_days));
  const p = data.params;
  return (
    <section aria-labelledby="hero-title">
      <p className="text-sm text-muted">
        Heatwave days per year · {shortDate(p.start_date)} to {shortDate(p.end_date)}
        {data.cached && <span className="ml-2 rounded bg-mist px-2 py-0.5 text-xs">Cached result</span>}
      </p>
      <h1 id="hero-title" className="mt-1 text-4xl font-bold sm:text-5xl">{regionLabel(data.region)}</h1>
      <p className="mt-2 max-w-prose text-sm text-muted">
        {p.min_duration}+ consecutive days above {temp(summary.threshold_c)}, the {p.percentile}th percentile of daily maximum temperature
        {data.region.type === "bbox" ? ` (mean of ${data.region.sample_points} grid points)` : ""}.
      </p>
      <div role="img" aria-label={`Heatwave days per year from ${annual[0]?.year} to ${annual.at(-1)?.year}, darker means more`}
        className="mt-5 flex h-36 gap-[2px] overflow-hidden rounded-lg border border-line sm:h-44">
        {annual.map((a, i) => (
          <div key={a.year} title={`${a.year}: ${a.heatwave_days} heatwave day${a.heatwave_days === 1 ? "" : "s"}${a.complete ? "" : " (incomplete year)"}`}
            className={`stripe-enter flex-1 ${a.complete ? "" : "hatch"}`}
            style={{ animationDelay: `${i * 12}ms`, background: a.complete ? heatColor(a.heatwave_days, max) : undefined }} />
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
