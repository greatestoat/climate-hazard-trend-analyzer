import { useMemo, useState } from "react";
import { DurationChart, FrequencyChart, HeatDaysChart } from "../components/Charts";
import { ControlPanel } from "../components/ControlPanel";
import { EventsTable } from "../components/EventsTable";
import { InsightsPanel, MethodPanel } from "../components/InsightsPanel";
import { EmptyView, ErrorView, LoadingView } from "../components/StateViews";
import { StripesHero } from "../components/StripesHero";
import { SummaryCards } from "../components/SummaryCards";
import { useAnalysis } from "../hooks/useAnalysis";
import { buildRequest, defaultForm, validateForm } from "../lib/request";
import { regionLabel } from "../lib/format";

export default function Dashboard() {
  const [form, setForm] = useState(defaultForm);
  const { state, run, retry } = useAnalysis();
  const errors = useMemo(() => validateForm(form), [form]);
  const submit = () => { if (errors.length === 0) void run(buildRequest(form)); };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[340px_1fr]">
      <aside className="rail scrollbar-hidden bg-ink text-paper lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto no-print">
        <ControlPanel form={form} onChange={setForm} onSubmit={submit} loading={state.status === "loading"} errors={state.status === "idle" ? [] : errors} />
      </aside>

      <main className="min-w-0 space-y-6 p-4 sm:p-8">
        {state.status === "idle" && (
          <EmptyView title="Choose a place and a period">
            Pick a city or draw a custom box, set the dates, then run the analysis. Results are calculated from Open-Meteo’s historical daily maximum temperatures.
            {errors.length > 0 && <span className="mt-3 block text-ink">Next step: {errors[0]}</span>}
          </EmptyView>
        )}
        {state.status === "loading" && <LoadingView />}
        {state.status === "error" && <ErrorView error={state.error} onRetry={retry} />}
        {state.status === "success" && (
          <>
            <div className="flex justify-end no-print">
              <button type="button" onClick={() => window.print()} className="rounded-md border border-line bg-surface px-4 py-2.5 text-sm font-semibold text-ink shadow-sm transition hover:border-ember hover:bg-ember/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-tide">
                Save report as PDF
              </button>
            </div>
            <section className="print-report-header hidden">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Analysis report</p>
                <h1 className="mt-1 text-2xl font-bold">{regionLabel(state.data.region)}</h1>
                <p className="mt-1 text-sm text-muted">{state.data.params.start_date} to {state.data.params.end_date} · Heatwave analysis</p>
              </div>
              <p className="hidden text-xs text-muted print:block">Created {new Date(state.data.created_at).toLocaleString()}</p>
            </section>
            <StripesHero data={state.data} />
            <SummaryCards result={state.data.result} />
            <div className="grid gap-6 xl:grid-cols-2">
              <FrequencyChart annual={state.data.result.annual} />
              <HeatDaysChart annual={state.data.result.annual} />
            </div>
            <DurationChart annual={state.data.result.annual} />
            <div className="grid gap-6 xl:grid-cols-2">
              <InsightsPanel data={state.data} />
              <MethodPanel data={state.data} />
            </div>
            <div className="no-print"><EventsTable key={state.data.id} analysis={state.data} /></div>
          </>
        )}
      </main>
    </div>
  );
}
