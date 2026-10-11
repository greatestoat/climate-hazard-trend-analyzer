export interface CityResult {
  id: number | null;
  name: string;
  country: string | null;
  admin1: string | null;
  latitude: number;
  longitude: number;
  timezone: string | null;
  population: number | null;
}

export type RegionInput =
  | { type: "city"; name: string; country?: string | null; latitude: number; longitude: number }
  | { type: "bbox"; name?: string | null; south: number; west: number; north: number; east: number };

export type ThresholdMethod = "period" | "seasonal";
export type Hazard = "heatwave" | "cold_wave" | "heavy_rainfall";

export interface AnalysisRequest {
  region: RegionInput;
  start_date: string;
  end_date: string;
  hazard: Hazard;
  percentile: number;
  min_duration: number;
  threshold_method: ThresholdMethod;
}

export interface AnnualStat {
  year: number;
  complete: boolean;
  expected_days: number;
  valid_days: number;
  coverage_pct: number;
  event_count: number;
  event_days: number;
  heatwave_days?: number;
  mean_duration_days: number | null;
  max_duration_days: number | null;
  peak_temp_c?: number | null;
  mean_tmax_c?: number | null;
  rolling_event_days?: number | null;
  trend_event_days?: number | null;
  extreme_value?: number | null;
  rolling_heatwave_days?: number | null;
  rolling_event_count: number | null;
  trend_heatwave_days?: number | null;
  trend_event_count: number | null;
}

export interface Trend {
  available: boolean;
  n_years: number;
  reason?: string;
  slope_per_year?: number;
  slope_per_decade?: number;
  r_squared?: number;
  p_value?: number;
  std_err?: number;
  direction?: "increasing" | "decreasing" | "flat";
}

export interface MannKendallTrend {
  available: boolean;
  n_years: number;
  reason?: string;
  tau?: number;
  p_value?: number;
  direction?: "increasing" | "decreasing" | "flat";
}

export interface PctChange {
  valid: boolean;
  pct_change: number | null;
  reason: string | null;
  early_mean?: number;
  late_mean?: number;
  early_period?: [number, number];
  late_period?: [number, number];
}

export interface Insight {
  id: string;
  severity: "info" | "warning" | "notice";
  title: string;
  text: string;
}

export interface Quality {
  rows_received: number;
  invalid_rows: number;
  duplicates_removed: number;
  outliers_removed: number;
  interpolated_days: number;
  total_days: number;
  valid_days: number;
  missing_days: number;
  missing_pct: number;
  source?: "open-meteo" | "cache" | "stale_cache";
}

export interface Summary {
  threshold_value: number;
  unit: "C" | "mm";
  total_events: number;
  total_event_days: number;
  total_heatwave_days?: number;
  mean_duration_days: number | null;
  longest_event: { start: string; end: string; duration_days: number } | null;
  extreme_value: number | null;
  extreme_date: string | null;
  peak_temp_c?: number | null;
  peak_date?: string | null;
  mean_events_per_year: number | null;
  mean_event_days_per_year: number | null;
  mean_heatwave_days_per_year?: number | null;
  years_in_range: number;
  complete_years: number;
  incomplete_years: number[];
  most_active_year: { year: number; event_days: number } | null;
}

export interface AnalysisResult {
  summary: Summary;
  annual: AnnualStat[];
  trend: { event_days?: Trend; event_count: Trend; heatwave_days?: Trend };
  mann_kendall?: { event_days: MannKendallTrend; event_count: MannKendallTrend };
  changes: { event_days?: PctChange; event_count: PctChange; heatwave_days?: PctChange };
  quality: Quality;
  insights: Insight[];
}

export interface Analysis {
  id: string;
  status: "completed";
  hazard: Hazard;
  created_at: string;
  region: RegionInput & { key: string; representation: string; sample_points: number };
  params: { start_date: string; end_date: string; percentile: number; min_duration: number; threshold_method: ThresholdMethod };
  result: AnalysisResult;
  warnings: string[];
  events_total: number;
  cached?: boolean;
}

export interface HeatwaveEvent {
  start: string;
  end: string;
  year: number;
  duration_days: number;
  extreme_value: number;
  extreme_date: string;
  mean_value: number;
  mean_excess: number;
  cumulative_excess: number;
  threshold_value: number;
  peak_temp_c?: number;
  peak_date?: string;
  mean_temp_c?: number;
  mean_excess_c?: number;
  cumulative_excess_c?: number;
  threshold_c?: number;
}

export type EventSort = "start" | "duration" | "peak" | "intensity";

export interface EventsPage {
  analysis_id: string;
  total: number;
  page: number;
  page_size: number;
  items: HeatwaveEvent[];
}
