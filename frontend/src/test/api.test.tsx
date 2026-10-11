import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildTiles } from "../components/SummaryCards";
import { EmptyView, ErrorView } from "../components/StateViews";
import { ApiError, createAnalysis, fetchEvents } from "../services/api";
import type { AnalysisResult } from "../types/api";

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));

describe("api service", () => {
  it("parses structured backend errors", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json({ error: { code: "upstream_timeout", message: "Open-Meteo timed out." } }, 504)));
    await expect(createAnalysis({} as never)).rejects.toMatchObject({ code: "upstream_timeout", status: 504, message: "Open-Meteo timed out." });
  });
  it("reports network failure clearly", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("failed"))));
    await expect(fetchEvents("a".repeat(32), { sort: "start", order: "asc", page: 1, pageSize: 10 })).rejects.toMatchObject({ code: "network_error" });
  });
  it("sends event query parameters", async () => {
    const f = vi.fn(() => json({ analysis_id: "x", total: 0, page: 2, page_size: 10, items: [] }));
    vi.stubGlobal("fetch", f);
    await fetchEvents("a".repeat(32), { year: 2019, sort: "duration", order: "desc", page: 2, pageSize: 10 });
    const url = (f.mock.calls[0] as unknown as [string])[0];
    expect(url).toContain("year=2019");
    expect(url).toContain("sort=duration");
    expect(url).toContain("page=2");
  });
});

describe("state views", () => {
  it("calls retry from the error view", async () => {
    const retry = vi.fn();
    render(<ErrorView error={new ApiError("Boom", 0, "network_error")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
  });
  it("renders an empty view", () => {
    render(<EmptyView title="Nothing here">Try again</EmptyView>);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});

describe("summary tiles use API values", () => {
  const base = {
    summary: { threshold_c: 40, total_events: 7, total_heatwave_days: 31, mean_duration_days: 4.43, longest_event: { start: "2019-05-01", end: "2019-05-09", duration_days: 9 },
      peak_temp_c: 45.2, peak_date: "2019-05-04", mean_events_per_year: 0.2, mean_heatwave_days_per_year: 0.9, years_in_range: 30, complete_years: 30, incomplete_years: [], most_active_year: null },
    trend: { heatwave_days: { available: true, n_years: 30, slope_per_decade: 1.234, r_squared: 0.31, p_value: 0.0004, significant: true }, event_count: { available: false, n_years: 0 } },
    changes: { heatwave_days: { valid: false, pct_change: null, reason: "No baseline." }, event_count: { valid: false, pct_change: null, reason: "x" } },
  } as unknown as AnalysisResult;
  it("shows real numbers and explains undefined changes", () => {
    const t = Object.fromEntries(buildTiles(base).map((x) => [x.label, x]));
    expect(t["Heatwave events"].value).toBe("7");
    expect(t["Peak temperature"].value).toBe("45.2 °C");
    expect(t["Trend"].value).toBe("+1.23 days/decade");
    expect(t["Trend"].note).toContain("< 0.001");
    expect(t["Late vs early period"].value).toBe("—");
    expect(t["Late vs early period"].note).toBe("No baseline.");
  });
});
