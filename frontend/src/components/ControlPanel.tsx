import type { ReactNode } from "react";
import type { FormState } from "../lib/request";
import { MIN_START } from "../lib/request";
import { CitySearch } from "./CitySearch";
import { RegionMap } from "./RegionMap";
import "leaflet/dist/leaflet.css";
import type { Hazard } from "../types/api";

interface Props {
  form: FormState;
  onChange: (f: FormState) => void;
  onSubmit: () => void;
  loading: boolean;
  errors: string[];
}

const input = "w-full rounded-md border border-white/20 bg-ink-soft px-3 py-2 text-sm text-paper placeholder:text-paper/40 [color-scheme:dark]";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-paper/70">{label}</span>
      {children}
    </label>
  );
}

export function ControlPanel({ form, onChange, onSubmit, loading, errors }: Props) {
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => onChange({ ...form, [k]: v });
  const setBox = (k: keyof FormState["bbox"], v: string) => onChange({ ...form, bbox: { ...form.bbox, [k]: v } });
  const chooseHazard = (hazard: Hazard) => onChange({
    ...form,
    hazard,
    percentile: hazard === "cold_wave" ? 5 : 95,
    minDuration: hazard === "heavy_rainfall" ? 1 : 3,
  });
  const hazards: { id: Hazard; label: string }[] = [
    { id: "heatwave", label: "Heatwave" },
    { id: "cold_wave", label: "Cold wave" },
    { id: "heavy_rainfall", label: "Heavy rainfall" },
  ];
  const coords = [form.bbox.south, form.bbox.west, form.bbox.north, form.bbox.east].map(Number);
  const hasBoxCenter = coords.every(Number.isFinite)
    && [form.bbox.south, form.bbox.west, form.bbox.north, form.bbox.east].every((v) => v.trim() !== "")
    && coords[0] >= -90 && coords[2] <= 90 && coords[1] >= -180 && coords[3] <= 180
    && coords[0] < coords[2] && coords[1] < coords[3];
  const mapCenter: [number, number] = hasBoxCenter
    ? [(coords[0] + coords[2]) / 2, (coords[1] + coords[3]) / 2]
    : form.city ? [form.city.latitude, form.city.longitude] : [20, 78];
  const today = new Date().toISOString().slice(0, 10);

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="flex min-h-full flex-col gap-7 p-6">
      <div className="flex items-center gap-3">
        <div aria-hidden className="flex h-9 w-9 gap-[2px] overflow-hidden rounded">
          {["#f7ead2", "#efc77a", "#e9a23b", "#c2401c", "#5e0f12"].map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}
        </div>
        <div>
          <p className="font-display text-lg font-bold leading-tight">Climate Hazard</p>
          <p className="text-xs text-paper/60">Trend Analyzer</p>
        </div>
      </div>

      <fieldset className="space-y-3">
        <legend className="mb-2 font-display text-sm font-bold">Region</legend>
        <div role="tablist" aria-label="Region type" className="grid grid-cols-2 rounded-md bg-ink-soft p-1 text-sm">
          {(["city", "bbox"] as const).map((m) => (
            <button type="button" key={m} role="tab" aria-selected={form.mode === m} onClick={() => set("mode", m)}
              className={`rounded px-3 py-1.5 font-medium ${form.mode === m ? "bg-paper text-ink" : "text-paper/70 hover:text-paper"}`}>
              {m === "city" ? "City" : "Custom box"}
            </button>
          ))}
        </div>
        {form.mode === "city" ? (
          <CitySearch selected={form.city} onSelect={(c) => set("city", c)} />
        ) : (
          <div className="space-y-3">
            <RegionMap bbox={form.bbox} center={mapCenter} onBoxChange={(bbox) => onChange({ ...form, bbox })} />
            <Field label="Name (optional)">
              <input className={input} value={form.bbox.name} onChange={(e) => setBox("name", e.target.value)} placeholder="e.g. Deccan Plateau" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              {([["north", "North lat"], ["south", "South lat"], ["west", "West lon"], ["east", "East lon"]] as const).map(([k, l]) => (
                <Field key={k} label={l}>
                  <input className={input} inputMode="decimal" value={form.bbox[k]} onChange={(e) => setBox(k, e.target.value)} placeholder="0.0" />
                </Field>
              ))}
            </div>
            <p className="text-xs text-paper/60">Daily weather is averaged over a 3×3 grid inside the box (max 10° per side).</p>
          </div>
        )}
      </fieldset>

      <fieldset className="space-y-3">
        <legend className="mb-2 font-display text-sm font-bold">Period</legend>
        <div className="grid grid-cols-2 gap-3">
          <Field label="From"><input type="date" className={input} min={MIN_START} max={today} value={form.start} onChange={(e) => set("start", e.target.value)} /></Field>
          <Field label="To"><input type="date" className={input} min={MIN_START} max={today} value={form.end} onChange={(e) => set("end", e.target.value)} /></Field>
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="mb-2 font-display text-sm font-bold">Hazard</legend>
        {hazards.map((h) => (
          <label key={h.id} className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition ${h.id === form.hazard ? "border-amber bg-ink-soft" : "border-white/10 hover:border-white/30"}`}>
            <input type="radio" name="hazard" checked={h.id === form.hazard} onChange={() => chooseHazard(h.id)} className="accent-amber" />
            <span className="flex-1">{h.label}</span>
          </label>
        ))}
      </fieldset>

      <details className="group">
        <summary className="cursor-pointer font-display text-sm font-bold">Detection settings</summary>
        <div className="mt-3 space-y-3">
          <Field label={form.hazard === "cold_wave" ? "Lower-tail percentile" : form.hazard === "heavy_rainfall" ? "Wet-day rainfall percentile" : "Heat threshold percentile"}>
            <input type="number" min={form.hazard === "cold_wave" ? 1 : 90} max={form.hazard === "cold_wave" ? 10 : 99} step={0.5} className={input} value={form.percentile} onChange={(e) => set("percentile", Number(e.target.value))} />
          </Field>
          <Field label="Minimum event duration (days)">
            <input type="number" min={form.hazard === "heavy_rainfall" ? 1 : 3} max={14} step={1} className={input} value={form.minDuration} onChange={(e) => set("minDuration", Number(e.target.value))} />
          </Field>
          <Field label="Threshold method">
            <select className={input} value={form.method} onChange={(e) => set("method", e.target.value as FormState["method"])}>
              <option value="period">One threshold for the whole period</option>
              <option value="seasonal">Seasonal (per calendar day)</option>
            </select>
          </Field>
          <p className="text-xs text-paper/60">
            {form.hazard === "heatwave" && "Heatwave: daily maximum temperature above the selected upper percentile."}
            {form.hazard === "cold_wave" && "Cold wave: daily minimum temperature below the selected lower percentile."}
            {form.hazard === "heavy_rainfall" && "Heavy rainfall: daily total above the selected percentile of wet days (at least 1 mm)."}
          </p>
        </div>
      </details>

      <div className="mt-auto space-y-3">
        {errors.length > 0 && (
          <ul className="space-y-1 text-xs text-amber" aria-live="polite">{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        )}
        <button type="submit" disabled={loading || errors.length > 0}
          className="w-full rounded-md bg-amber px-4 py-2.5 text-sm font-bold text-ink hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50">
          {loading ? "Analysing…" : "Run analysis"}
        </button>
      </div>
    </form>
  );
}
