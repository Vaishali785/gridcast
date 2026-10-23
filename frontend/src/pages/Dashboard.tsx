import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import type { Metadata } from "../types/api";
import { Controls, type ControlState } from "../components/Controls";
import { DataQuality } from "../components/DataQuality";
import { ErrorAnalysis } from "../components/ErrorAnalysis";
import { ErrorTable } from "../components/ErrorTable";
import { ForecastChart } from "../components/ForecastChart";
import { Section, ErrorBox, Skeleton } from "../components/States";
import { SummaryCards } from "../components/SummaryCards";
import { VintagePanel } from "../components/VintagePanel";
import { fmtDateTime } from "../lib/format";

export function Dashboard({ meta }: { meta: Metadata }) {
  const [ctl, setCtl] = useState<ControlState>({ start: meta.window_start, end: meta.window_end, mode: "cutoff", asOf: "" });
  const [selected, setSelected] = useState<string | null>(null);

  const vt = useAsync((s) => api.vintageTimes(ctl.start, ctl.end, s), [ctl.start, ctl.end, meta.last_successful_refresh]);
  const vintages = vt.data?.vintage_times ?? [];
  // keep a valid vintage selected when the range changes
  useEffect(() => {
    if (ctl.mode === "vintage" && vintages.length && !vintages.some((v) => v.publish_time === ctl.asOf)) setCtl((c) => ({ ...c, asOf: vintages[vintages.length - 1].publish_time }));
  }, [vintages, ctl.mode, ctl.asOf]);

  const ready = ctl.mode !== "vintage" || !!ctl.asOf;
  const an = useAsync(ready ? (s) => api.analysis({ start: ctl.start, end: ctl.end, mode: ctl.mode, asOf: ctl.asOf }, s) : null,
    [ctl.start, ctl.end, ctl.mode, ctl.asOf, ready, meta.last_successful_refresh]);
  const a = an.data;

  const firstPair = useMemo(() => a?.series.find((r) => r.forecast_mw != null && r.actual_mw != null)?.start_time ?? null, [a]);
  useEffect(() => { if (!selected && firstPair) setSelected(firstPair); }, [selected, firstPair]);
  const select = (iso: string) => { setSelected(iso); document.getElementById("vintages")?.scrollIntoView({ behavior: "smooth" }); };

  return (
    <div className="space-y-8">
      <Section id="overview" title="Wind forecast accuracy" subtitle="Compare the wind forecast available when day-ahead purchases are made with what the wind actually delivered.">
        <Controls meta={meta} value={ctl} vintages={vintages} onChange={setCtl} />
        {a && a.is_retrospective && (
          <div role="status" className="mt-3 rounded border border-warn/40 bg-warnsoft text-warn px-4 py-3 text-sm">
            <strong>Retrospective view.</strong> {a.summary.n_lookahead_intervals.toLocaleString("en-GB")} half-hours use a forecast published <em>after</em> the decision cutoff
            {a.mode === "vintage" && a.as_of ? ` (forecasts up to ${fmtDateTime(a.as_of)})` : ""}. This information was not available when the purchase decision was made, so these metrics overstate decision-time accuracy.
          </div>
        )}
        {a && !a.is_retrospective && (
          <p className="mt-3 text-xs text-muted">Decision-time view: every forecast was published at or before its {a.cutoff.local_time} {a.cutoff.timezone} cutoff on the day before delivery. No later forecasts are used.</p>
        )}
        <div className={`mt-4 ${an.loading && a ? "opacity-60" : ""}`}>
          {an.error ? <ErrorBox error={an.error} onRetry={an.reload} /> : !a ? <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-24" />)}</div> : <SummaryCards a={a} />}
        </div>
      </Section>

      <Section id="forecast" title="Forecast vs actual" subtitle={a?.mode_label}>
        {a ? <ForecastChart series={a.series} selected={selected} onSelect={setSelected} /> : <Skeleton className="h-[420px]" />}
      </Section>

      <Section id="vintages" title="Forecast vintages" subtitle="How the forecast for one half-hour changed as new WINDFOR publications arrived. Hollow points were published after the decision cutoff.">
        <VintagePanel startTime={selected} />
      </Section>

      <Section id="errors" title="Error analysis" subtitle="Error = forecast − actual. Positive means the forecast was too high.">
        {a ? (<div className="space-y-4">
          <ErrorAnalysis histogram={a.error_histogram} series={a.series} topErrors={a.top_errors} onSelect={select} />
          <ErrorTable rows={a.series} selected={selected} onSelect={select} />
        </div>) : <Skeleton className="h-96" />}
      </Section>

      <Section id="quality" title="Data quality &amp; assumptions">
        {a ? <DataQuality meta={meta} analysis={a} /> : <Skeleton className="h-40" />}
      </Section>
    </div>
  );
}
