export const COLORS = {
  ink: "#0e2a33", ember: "#c2401c", amber: "#e9a23b", tide: "#2a7b8c", muted: "#5d7279", line: "#d3dcda",
};

const RAMP = ["#f7ead2", "#efc77a", "#e9a23b", "#c2401c", "#5e0f12"];

const hex = (h: string): [number, number, number] =>
  [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];

/** Maps a value in [0, max] onto the heat ramp. The ratio is clamped; max <= 0 returns the coolest colour. */
export function heatColor(value: number, max: number): string {
  const t = max <= 0 ? 0 : Math.min(Math.max(value / max, 0), 1);
  const pos = t * (RAMP.length - 1);
  const i = Math.min(Math.floor(pos), RAMP.length - 2);
  const f = pos - i;
  const a = hex(RAMP[i]);
  const b = hex(RAMP[i + 1]);
  return `rgb(${a.map((c, k) => Math.round(c + (b[k] - c) * f)).join(",")})`;
}
