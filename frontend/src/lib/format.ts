export const dash = "—";

export const num = (v: number | null | undefined, digits = 1): string =>
  v === null || v === undefined || Number.isNaN(v)
    ? dash
    : v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: 0 });

export const temp = (v: number | null | undefined): string => (v === null || v === undefined ? dash : `${v.toFixed(1)} °C`);

export const signed = (v: number | null | undefined, digits = 1): string =>
  v === null || v === undefined ? dash : `${v > 0 ? "+" : ""}${v.toFixed(digits)}`;

export const pct = (v: number | null | undefined): string => (v === null || v === undefined ? dash : `${signed(v, 0)}%`);

export const shortDate = (iso: string): string =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

export const formatP = (p: number | undefined): string => (p === undefined ? dash : p < 0.001 ? "< 0.001" : p.toFixed(3));

export function regionLabel(r: { type: string; name?: string | null; south?: number; west?: number; north?: number; east?: number }): string {
  if (r.name) return r.name;
  if (r.type === "bbox") return `Box ${r.south}°, ${r.west}° to ${r.north}°, ${r.east}°`;
  return "Selected region";
}

export const isoDate = (d: Date): string => d.toISOString().slice(0, 10);
