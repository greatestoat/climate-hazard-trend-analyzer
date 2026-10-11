import type { ReactNode } from "react";
import { Bar, CartesianGrid, Cell, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COLORS } from "../lib/colors";
import { num } from "../lib/format";
import type { AnnualStat } from "../types/api";

export function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <figure className="rounded-lg border border-line bg-surface p-5">
      <figcaption className="mb-4">
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="text-sm text-muted">{subtitle}</p>
      </figcaption>
      <div className="h-72">{children}</div>
    </figure>
  );
}

interface TipProps {
  active?: boolean;
  payload?: ReadonlyArray<{ payload?: AnnualStat }>;
  lines: (a: AnnualStat) => [string, string][];
}

function YearTooltip({ active, payload, lines }: TipProps) {
  const a = payload?.[0]?.payload;
  if (!active || !a) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-bold">{a.year}{!a.complete && <span className="ml-1 font-normal text-muted">(incomplete, {a.coverage_pct}% coverage)</span>}</p>
      {lines(a).map(([k, v]) => (
        <p key={k} className="flex justify-between gap-4"><span className="text-muted">{k}</span><span className="font-semibold">{v}</span></p>
      ))}
    </div>
  );
}

const axis = { tick: { fontSize: 12, fill: COLORS.muted }, stroke: COLORS.line } as const;
const margin = { top: 8, right: 8, left: -12, bottom: 0 };
const common = (
  <>
    <CartesianGrid stroke={COLORS.line} vertical={false} />
    <XAxis dataKey="year" {...axis} minTickGap={22} />
  </>
);

export function FrequencyChart({ annual }: { annual: AnnualStat[] }) {
  return (
    <ChartCard title="Heatwave frequency" subtitle="Events starting each year, with a 5-year average and fitted trend. Faded bars are incomplete years.">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={annual} margin={margin}>
          {common}
          <YAxis allowDecimals={false} {...axis} />
          <Tooltip content={<YearTooltip lines={(a) => [["Events", String(a.event_count)], ["5-yr average", num(a.rolling_event_count)], ["Trend", num(a.trend_event_count)]]} />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="event_count" name="Events" radius={[2, 2, 0, 0]}>
            {annual.map((a) => <Cell key={a.year} fill={COLORS.ember} fillOpacity={a.complete ? 1 : 0.3} />)}
          </Bar>
          <Line dataKey="rolling_event_count" name="5-year average" stroke={COLORS.ink} strokeWidth={2} dot={false} />
          <Line dataKey="trend_event_count" name="Trend" stroke={COLORS.tide} strokeWidth={2} strokeDasharray="6 4" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

interface DotProps { cx?: number; cy?: number; payload?: AnnualStat }
function YearDot({ cx, cy, payload }: DotProps) {
  if (cx === undefined || cy === undefined || !payload) return null;
  return <circle cx={cx} cy={cy} r={3.5} stroke={COLORS.ember} strokeWidth={2} fill={payload.complete ? COLORS.ember : "#fff"} />;
}

export function HeatDaysChart({ annual }: { annual: AnnualStat[] }) {
  return (
    <ChartCard title="Heatwave days per year" subtitle="Total days spent inside heatwaves. Hollow points are incomplete years, excluded from the trend line.">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={annual} margin={margin}>
          {common}
          <YAxis allowDecimals={false} {...axis} />
          <Tooltip content={<YearTooltip lines={(a) => [["Heatwave days", String(a.heatwave_days)], ["5-yr average", num(a.rolling_heatwave_days)], ["Trend", num(a.trend_heatwave_days)]]} />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line dataKey="heatwave_days" name="Heatwave days" stroke={COLORS.ember} strokeWidth={1.5} dot={<YearDot />} activeDot={{ r: 5 }} />
          <Line dataKey="rolling_heatwave_days" name="5-year average" stroke={COLORS.ink} strokeWidth={2} dot={false} />
          <Line dataKey="trend_heatwave_days" name="Trend" stroke={COLORS.tide} strokeWidth={2} strokeDasharray="6 4" dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function DurationChart({ annual }: { annual: AnnualStat[] }) {
  return (
    <ChartCard title="Event duration" subtitle="Mean and longest heatwave beginning each year, in days. Years without events have no bar.">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={annual} margin={margin}>
          {common}
          <YAxis allowDecimals={false} {...axis} />
          <Tooltip content={<YearTooltip lines={(a) => [["Mean duration", a.mean_duration_days === null ? "—" : `${num(a.mean_duration_days)} d`], ["Longest", a.max_duration_days === null ? "—" : `${a.max_duration_days} d`], ["Events", String(a.event_count)]]} />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="mean_duration_days" name="Mean duration" fill={COLORS.amber} radius={[2, 2, 0, 0]} />
          <Bar dataKey="max_duration_days" name="Longest event" fill={COLORS.ember} radius={[2, 2, 0, 0]} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
