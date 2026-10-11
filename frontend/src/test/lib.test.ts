import { describe, expect, it } from "vitest";
import { heatColor } from "../lib/colors";
import { pct, regionLabel, signed } from "../lib/format";
import { buildRequest, defaultForm, validateForm } from "../lib/request";

describe("format helpers", () => {
  it("formats missing values safely", () => {
    expect(pct(null)).toBe("—");
    expect(signed(undefined)).toBe("—");
    expect(pct(12.4)).toBe("+12%");
    expect(pct(-8)).toBe("-8%");
  });
  it("labels regions", () => {
    expect(regionLabel({ type: "city", name: "Hyderabad" })).toBe("Hyderabad");
    expect(regionLabel({ type: "bbox", south: 1, west: 2, north: 3, east: 4 })).toContain("Box");
  });
});

describe("heatColor", () => {
  it("clamps and handles zero max", () => {
    expect(heatColor(0, 0)).toBe(heatColor(0, 10));
    expect(heatColor(99, 10)).toBe(heatColor(10, 10));
    expect(heatColor(0, 10)).not.toBe(heatColor(10, 10));
  });
});

describe("form validation", () => {
  const now = new Date("2026-10-11T00:00:00Z");
  it("defaults to a 35-year period ending last year", () => {
    const f = defaultForm(now);
    expect(f.start).toBe("1991-01-01");
    expect(f.end).toBe("2025-12-31");
    expect(f.hazard).toBe("heatwave");
  });
  it("requires a city in city mode", () => {
    expect(validateForm(defaultForm(now), now)).toContain("Choose a city from the search results.");
  });
  it("validates bounding boxes", () => {
    const f = { ...defaultForm(now), mode: "bbox" as const, bbox: { name: "", south: "20", west: "70", north: "10", east: "90" } };
    const errs = validateForm(f, now);
    expect(errs.some((e) => e.includes("South must be less"))).toBe(true);
    expect(errs.some((e) => e.includes("at most"))).toBe(true);
  });
  it("rejects short and future ranges", () => {
    const f = { ...defaultForm(now), mode: "bbox" as const, bbox: { name: "", south: "1", west: "1", north: "2", east: "2" }, start: "2024-01-01", end: "2026-01-01" };
    expect(validateForm(f, now).some((e) => e.includes("3 years"))).toBe(true);
    expect(validateForm({ ...f, end: "2030-01-01" }, now).some((e) => e.includes("future"))).toBe(true);
  });
  it("builds a bbox request", () => {
    const f = { ...defaultForm(now), mode: "bbox" as const, bbox: { name: " Deccan ", south: "10", west: "70", north: "15", east: "75" } };
    const r = buildRequest(f);
    expect(r.region).toEqual({ type: "bbox", name: "Deccan", south: 10, west: 70, north: 15, east: 75 });
    expect(r.min_duration).toBe(3);
  });
});
