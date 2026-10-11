import type { AnalysisRequest, CityResult, Hazard, ThresholdMethod } from "../types/api";
import { isoDate } from "./format";

export interface FormState {
  mode: "city" | "bbox";
  city: CityResult | null;
  bbox: { name: string; south: string; west: string; north: string; east: string };
  start: string;
  end: string;
  hazard: Hazard;
  percentile: number;
  minDuration: number;
  method: ThresholdMethod;
}

export const MAX_BBOX_SPAN = 10;
export const MIN_START = "1940-01-01";

export function defaultForm(now = new Date()): FormState {
  const lastYear = now.getUTCFullYear() - 1;
  return {
    mode: "city",
    city: null,
    bbox: { name: "", south: "", west: "", north: "", east: "" },
    start: `${lastYear - 34}-01-01`,
    end: `${lastYear}-12-31`,
    hazard: "heatwave",
    percentile: 95,
    minDuration: 3,
    method: "period",
  };
}

export function validateForm(f: FormState, now = new Date()): string[] {
  const errs: string[] = [];
  if (f.mode === "city") {
    if (!f.city) errs.push("Choose a city from the search results.");
  } else {
    const [s, w, n, e] = [f.bbox.south, f.bbox.west, f.bbox.north, f.bbox.east].map((v) => (v.trim() === "" ? NaN : Number(v)));
    if ([s, w, n, e].some(Number.isNaN)) errs.push("Enter all four bounding-box coordinates.");
    else {
      if (s < -90 || n > 90 || w < -180 || e > 180) errs.push("Latitude must be within ±90 and longitude within ±180.");
      if (s >= n) errs.push("South must be less than north.");
      if (w >= e) errs.push("West must be less than east.");
      if (n - s > MAX_BBOX_SPAN || e - w > MAX_BBOX_SPAN) errs.push(`The box may span at most ${MAX_BBOX_SPAN}° in each direction.`);
    }
  }
  if (!f.start || !f.end) errs.push("Choose a start and end date.");
  else {
    const days = (Date.parse(f.end) - Date.parse(f.start)) / 86_400_000;
    if (f.start < MIN_START) errs.push("Data starts on 1940-01-01.");
    if (f.end > isoDate(now)) errs.push("The end date cannot be in the future.");
    if (days <= 0) errs.push("The start date must be before the end date.");
    else if (days < 3 * 365) errs.push("Choose at least 3 years so a threshold and trend can be estimated.");
  }
  if (f.hazard === "cold_wave" ? !(f.percentile >= 1 && f.percentile <= 10) : !(f.percentile >= 90 && f.percentile <= 99)) {
    errs.push(f.hazard === "cold_wave" ? "Cold-wave percentile must be between 1 and 10." : "Percentile must be between 90 and 99.");
  }
  if (f.minDuration < (f.hazard === "heavy_rainfall" ? 1 : 3) || f.minDuration > 14) errs.push("Minimum duration is outside the allowed range.");
  return errs;
}

export function buildRequest(f: FormState): AnalysisRequest {
  const region: AnalysisRequest["region"] =
    f.mode === "city" && f.city
      ? { type: "city", name: f.city.name, country: f.city.country, latitude: f.city.latitude, longitude: f.city.longitude }
      : {
          type: "bbox",
          name: f.bbox.name.trim() || null,
          south: Number(f.bbox.south), west: Number(f.bbox.west), north: Number(f.bbox.north), east: Number(f.bbox.east),
        };
  return {
    region, start_date: f.start, end_date: f.end, hazard: f.hazard,
    percentile: f.percentile, min_duration: f.minDuration, threshold_method: f.method,
  };
}
