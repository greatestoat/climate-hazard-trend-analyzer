import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import Dashboard from "../pages/Dashboard";
import analysis from "./fixtures/analysis.json";
import cities from "./fixtures/cities.json";
import events from "./fixtures/events.json";

beforeAll(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => vi.unstubAllGlobals());

const res = (b: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(b), { status }));

async function pickCity() {
  await userEvent.type(screen.getByRole("combobox", { name: /search for a city/i }), "hyderabad");
  await userEvent.click(await screen.findByRole("button", { name: /Hyderabad/ }));
}

describe("Dashboard (real backend payloads)", () => {
  it("runs an analysis and renders results from the API", async () => {
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/api/cities")) return res(cities);
      if (url.includes("/events")) return res(events);
      if (init?.method === "POST") return res(analysis, 201);
      return res({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<Dashboard />);

    expect(screen.getByText("Choose a place and a period")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Heatwave" })).toBeChecked();
    await pickCity();
    await userEvent.click(screen.getByRole("button", { name: "Run analysis" }));

    const s = analysis.result.summary;
    expect(await screen.findByRole("heading", { level: 1, name: "Hyderabad" })).toBeInTheDocument();
    const cards = screen.getByRole("region", { name: "Summary statistics" });
    expect(within(cards).getByText(String(s.total_events))).toBeInTheDocument();
    expect(within(cards).getByText(`${s.peak_temp_c!.toFixed(1)} °C`)).toBeInTheDocument();
    for (const i of analysis.result.insights) expect(screen.getByText(i.title)).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("row").length).toBeGreaterThan(1));

    const post = fetchMock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST")!;
    const body = JSON.parse((post[1] as RequestInit).body as string);
    expect(body).toMatchObject({ hazard: "heatwave", percentile: 95, min_duration: 3, region: { type: "city", name: "Hyderabad" } });
  });

  it("shows an error with retry, then recovers", async () => {
    let calls = 0;
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/api/cities")) return res(cities);
      if (url.includes("/events")) return res(events);
      if (init?.method === "POST" && calls++ === 0) return res({ error: { code: "upstream_timeout", message: "Open-Meteo timed out." } }, 504);
      return res(analysis, 201);
    }));
    render(<Dashboard />);
    await pickCity();
    await userEvent.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Open-Meteo timed out.");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Hyderabad" })).toBeInTheDocument();
  });
});
