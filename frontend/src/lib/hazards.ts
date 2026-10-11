import type { Hazard } from "../types/api";

export interface HazardLabels {
  name: string;
  eventDays: string;
  events: string;
  extreme: string;
  unit: string;
  measure: string;
}

const LABELS: Record<Hazard, HazardLabels> = {
  heatwave: { name: "Heatwave", eventDays: "Heatwave days", events: "Heatwave events", extreme: "Peak temperature", unit: "°C", measure: "daily maximum temperature" },
  cold_wave: { name: "Cold wave", eventDays: "Cold-wave days", events: "Cold-wave events", extreme: "Lowest temperature", unit: "°C", measure: "daily minimum temperature" },
  heavy_rainfall: { name: "Heavy rainfall", eventDays: "Heavy-rainfall days", events: "Heavy-rainfall events", extreme: "Highest daily rainfall", unit: "mm", measure: "daily precipitation" },
};

export const hazardLabels = (hazard: Hazard): HazardLabels => LABELS[hazard];
