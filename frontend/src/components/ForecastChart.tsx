import { useMemo } from "react";
import { Brush, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { IntervalRow } from "../types/api";
import { fmtDateTime, fmtDay, fmtMW, fmtSignedMW, fmtTime } from "../lib/format";

interface Point { t: number; forecast: number | null; actual: number | null; row: IntervalRow }

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const { row } = payload[0].payload;
  return (
    <div className="card p-3 text-xs shadow-md min-w-[220px]">
      <div className="font-medium">{fmtDateTime(row.start_time)} · SP {row.settlement_period}</div>
      <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 tabular-nums">
        <dt className="text-muted">Forecast</dt><dd className="text-right">{row.forecast_mw == null ? "unavailable" : fmtMW(row.forecast_mw)}</dd>
        <dt className="text-muted">Actual</dt><dd className="text-right">{row.actual_mw == null ? "unavailable" : fmtMW(row.actual_mw)}</dd>
        <dt className="text-muted">Error (F−A)</dt><dd className="text-right">{fmtSignedMW(row.error_mw)}</dd>
        <dt className="text-muted">Forecast published</dt><dd className="text-right">{fmtDateTime(row.forecast_publish_time)}</dd>
      </dl>
      {row.lookahead && <p className="mt-1.5 text-warn">Published after the decision cutoff</p>}
    </div>
  );
}

export function ForecastChart({ series, selected, onSelect }: { series: IntervalRow[]; selected: string | null; onSelect: (iso: string) => void }) {
  const data: Point[] = useMemo(() => series.map((r) => ({ t: Date.parse(r.start_time), forecast: r.forecast_mw, actual: r.actual_mw, row: r })), [series]);
  const multiDay = data.length > 96;
  return (
    <div className="card p-4">
      <div className="h-[380px]" role="img" aria-label="Line chart of forecast versus actual wind generation in megawatts">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
            onClick={(s: { activePayload?: { payload: Point }[] }) => { const p = s?.activePayload?.[0]?.payload; if (p) onSelect(p.row.start_time); }}>
            <CartesianGrid stroke="#E3E1DA" vertical={false} />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11, fill: "#5B6677" }}
              tickFormatter={(t: number) => (multiDay ? fmtDay(new Date(t).toISOString()) : fmtTime(new Date(t).toISOString()))} minTickGap={40} />
            <YAxis tick={{ fontSize: 11, fill: "#5B6677" }} tickFormatter={(v: number) => (v / 1000).toFixed(0)} width={44}
              label={{ value: "GW", position: "insideTopLeft", offset: -4, fontSize: 11, fill: "#5B6677" }} />
            <Tooltip content={<ChartTooltip />} />
            <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
            {selected && <ReferenceLine x={Date.parse(selected)} stroke="#0F1B2D" strokeDasharray="3 3" />}
            <Line name="Actual wind (MW)" dataKey="actual" stroke="#2F7D5B" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
            <Line name="Forecast (MW)" dataKey="forecast" stroke="#2A5C9E" strokeWidth={1.75} strokeDasharray="5 3" dot={false} connectNulls={false} isAnimationActive={false} />
            {multiDay && <Brush dataKey="t" height={24} stroke="#5B6677" tickFormatter={(t: number) => fmtDay(new Date(t).toISOString())} />}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-muted mt-2">Gaps in a line mean the value is unavailable for that half-hour — they are not zero generation. Click the chart to inspect a half-hour in the vintage panel.</p>
    </div>
  );
}
