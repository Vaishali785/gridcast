import { useMemo } from "react"
import {
	Brush,
	CartesianGrid,
	Legend,
	Line,
	LineChart,
	ReferenceLine,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts"
import { buildChartPoints, hasForecast, type ChartPoint } from "../lib/chart"
import { fmtDateTime, fmtDay, fmtMW, fmtSignedMW, fmtTime } from "../lib/format"
import type { IntervalRow } from "../types/api"

type Point = ChartPoint

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
	if (!active || !payload?.length) return null
	const { row } = payload[0].payload
	return (
		<div className="card p-3 text-xs shadow-md min-w-[220px]">
			<div className="font-medium">
				{fmtDateTime(row.start_time)} · SP {row.settlement_period}
			</div>
			<dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 tabular-nums">
				<dt className="text-muted">Forecast</dt>
				<dd className="text-right">
					{row.forecast_mw == null ? "unavailable" : fmtMW(row.forecast_mw)}
				</dd>
				<dt className="text-muted">Actual</dt>
				<dd className="text-right">
					{row.actual_mw == null ? "unavailable" : fmtMW(row.actual_mw)}
				</dd>
				<dt className="text-muted">Error (F−A)</dt>
				<dd className="text-right">{fmtSignedMW(row.error_mw)}</dd>
				<dt className="text-muted">Forecast published</dt>
				<dd className="text-right">{fmtDateTime(row.forecast_publish_time)}</dd>
			</dl>
			{row.lookahead && <p className="mt-1.5 text-warn">Published after the decision cutoff</p>}
		</div>
	)
}

export function ForecastChart({
	series,
	selected,
	onSelect,
}: {
	series: IntervalRow[]
	selected: string | null
	onSelect: (iso: string) => void
}) {
	const data: Point[] = useMemo(() => buildChartPoints(series), [series])
	const forecastPresent = useMemo(() => hasForecast(series), [series])
	const multiDay = data.length > 96
	return (
		<div className="card p-4">
			{!forecastPresent && (
				<p role="status" className="mb-2 rounded bg-warnsoft text-warn text-sm px-3 py-2">
					No forecast data available for this selection — only actual generation is shown.
				</p>
			)}
			<div
				className="h-[320px] sm:h-[380px]"
				role="img"
				aria-label="Line chart of forecast versus actual wind generation in megawatts"
			>
				<ResponsiveContainer>
					<LineChart
						data={data}
						margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
						onClick={(s: { activePayload?: { payload: Point }[] }) => {
							const p = s?.activePayload?.[0]?.payload
							if (p) onSelect(p.row.start_time)
						}}
					>
						<CartesianGrid stroke="#E3E1DA" vertical={false} />
						<XAxis
							dataKey="t"
							type="number"
							scale="time"
							domain={["dataMin", "dataMax"]}
							tick={{ fontSize: 11, fill: "#5B6677" }}
							tickFormatter={(t: number) =>
								multiDay ? fmtDay(new Date(t).toISOString()) : fmtTime(new Date(t).toISOString())
							}
							minTickGap={40}
						/>
						<YAxis
							tick={{ fontSize: 11, fill: "#5B6677" }}
							tickFormatter={(v: number) => (v / 1000).toFixed(0)}
							width={44}
							label={{
								value: "GW",
								position: "insideTopLeft",
								offset: -4,
								fontSize: 11,
								fill: "#5B6677",
							}}
						/>
						<Tooltip content={<ChartTooltip />} />
						<Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
						{selected && (
							<ReferenceLine x={Date.parse(selected)} stroke="#0F1B2D" strokeDasharray="3 3" />
						)}
						<Line
							name="Actual wind (MW)"
							dataKey="actual"
							stroke="#2F7D5B"
							strokeWidth={2}
							dot={false}
							connectNulls={false}
							isAnimationActive={false}
						/>
						<Line
							name="Forecast (MW)"
							dataKey="forecast"
							stroke="#2A5C9E"
							strokeWidth={1.75}
							strokeDasharray="5 3"
							dot={(p: { cx?: number; cy?: number; index?: number; payload?: Point }) =>
								p.payload?.isolatedForecast ? (
									<circle key={p.index} cx={p.cx} cy={p.cy} r={2.5} fill="#2A5C9E" />
								) : (
									<g key={p.index} />
								)
							}
							connectNulls={false}
							isAnimationActive={false}
						/>
						{multiDay && (
							<Brush
								dataKey="t"
								height={24}
								stroke="#5B6677"
								tickFormatter={(t: number) => fmtDay(new Date(t).toISOString())}
							/>
						)}
					</LineChart>
				</ResponsiveContainer>
			</div>
			<p className="text-xs text-muted mt-1">
				Gaps = data unavailable (not zero). Click the chart to inspect a half-hour under Forecast
				vintages.
			</p>
		</div>
	)
}
