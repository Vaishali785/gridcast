import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { fmtDateTime, fmtMW } from "../lib/format";
import { EmptyState, ErrorBox, Skeleton } from "./States";

export function VintagePanel({ startTime }: { startTime: string | null }) {
  const { data, error, loading, reload } = useAsync(startTime ? (s) => api.vintages(startTime, s) : null, [startTime]);
  if (!startTime) return <EmptyState title="Select a half-hour">Click the forecast chart or a row in the error table to see how the forecast for that interval evolved.</EmptyState>;
  if (error) return <ErrorBox error={error} onRetry={reload} />;
  if (!data) return <Skeleton className="h-72" />;
  if (!data.vintages.length) return <EmptyState title="No forecast vintages for this interval">Elexon returned no WINDFOR records for {fmtDateTime(startTime)}.</EmptyState>;

  const pts = data.vintages.map((v) => ({ t: Date.parse(v.publish_time), mw: v.forecast_mw, v }));
  const cutoffMs = Date.parse(data.cutoff_time);
  return (
    <div className={`grid lg:grid-cols-[1fr_320px] gap-4 ${loading ? "opacity-60" : ""}`}>
      <div className="card p-4">
        <div className="text-sm mb-2">Forecast for <strong>{fmtDateTime(data.start_time)}</strong> by publication time</div>
        <div className="h-[280px]" role="img" aria-label="Forecast value by publication time for the selected delivery interval">
          <ResponsiveContainer>
            <LineChart data={pts} margin={{ top: 8, right: 24, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="#E3E1DA" vertical={false} />
              <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: "#5B6677" }}
                tickFormatter={(t: number) => fmtDateTime(new Date(t).toISOString())} minTickGap={50} />
              <YAxis tick={{ fontSize: 11, fill: "#5B6677" }} tickFormatter={(v: number) => (v / 1000).toFixed(1)} width={44} domain={["auto", "auto"]} />
              <Tooltip formatter={(v: number) => fmtMW(v)} labelFormatter={(t: number) => `Published ${fmtDateTime(new Date(t).toISOString())}`} />
              <ReferenceLine x={cutoffMs} stroke="#9A5B00" strokeDasharray="4 3" label={{ value: "Decision cutoff", fontSize: 11, fill: "#9A5B00", position: "insideTopRight" }} />
              {data.actual_mw != null && <ReferenceLine y={data.actual_mw} stroke="#2F7D5B" strokeWidth={2} label={{ value: `Actual ${fmtMW(data.actual_mw)}`, fontSize: 11, fill: "#2F7D5B", position: "insideBottomRight" }} />}
              <Line type="stepAfter" dataKey="mw" stroke="#2A5C9E" strokeWidth={1.75} isAnimationActive={false}
                dot={(p: { cx?: number; cy?: number; payload?: { v: { available_at_cutoff: boolean } }; index?: number }) => (
                  <circle key={p.index} cx={p.cx} cy={p.cy} r={4} fill={p.payload?.v.available_at_cutoff ? "#2A5C9E" : "#fff"} stroke={p.payload?.v.available_at_cutoff ? "#2A5C9E" : "#9A5B00"} strokeWidth={2} />
                )} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-muted mt-2"><span className="inline-block w-2.5 h-2.5 rounded-full bg-forecast align-middle mr-1" />Available at decision cutoff · <span className="inline-block w-2.5 h-2.5 rounded-full border-2 border-warn align-middle mr-1 ml-2" />Published later (retrospective only)</p>
      </div>
      <div className="card overflow-auto max-h-[360px]">
        <table className="w-full text-xs tabular-nums">
          <thead className="sticky top-0 bg-surface text-left text-muted"><tr><th className="p-2 font-medium">Published (UK)</th><th className="p-2 font-medium text-right">Forecast</th><th className="p-2 font-medium text-right">Lead</th></tr></thead>
          <tbody>
            {[...data.vintages].reverse().map((v) => (
              <tr key={v.publish_time} className="border-t border-line">
                <td className="p-2">{fmtDateTime(v.publish_time)}{!v.available_at_cutoff && <span className="ml-1 text-warn" title="Published after the decision cutoff">●</span>}</td>
                <td className="p-2 text-right">{fmtMW(v.forecast_mw)}</td>
                <td className="p-2 text-right text-muted">{v.hours_before_delivery.toFixed(1)} h</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
