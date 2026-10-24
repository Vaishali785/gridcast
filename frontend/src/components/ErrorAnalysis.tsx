import { useMemo } from "react"
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	ReferenceLine,
	ResponsiveContainer,
	Tooltip,
	XAxis,
	YAxis,
} from "recharts"
import { fmtDateTime, fmtDay, fmtInt, fmtMW, fmtSignedMW } from "../lib/format"
import type { HistogramBin, IntervalRow } from "../types/api"

export function ErrorAnalysis({
	histogram,
	series,
	topErrors,
	onSelect,
}: {
	histogram: HistogramBin[]
	series: IntervalRow[]
	topErrors: IntervalRow[]
	onSelect: (iso: string) => void
}) {
	const over = useMemo(
		() => series.map((r) => ({ t: Date.parse(r.start_time), e: r.error_mw })),
		[series],
	)
	const bins = histogram.map((b) => ({
		...b,
		label: `${(b.bin_start_mw / 1000).toFixed(0)}`,
		mid: (b.bin_start_mw + b.bin_end_mw) / 2,
	}))
	return (
		<div className="grid lg:grid-cols-3 gap-4">
			<div className="card p-4">
				<div className="text-sm font-medium">Error distribution</div>
				<p className="text-xs text-muted mb-2">
					Half-hours by forecast - actual (1 GW bins, label = lower edge in GW)
				</p>
				<div className="h-[220px]" role="img" aria-label="Histogram of forecast errors">
					<ResponsiveContainer>
						<BarChart data={bins} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
							<CartesianGrid stroke="#E3E1DA" vertical={false} />
							<XAxis
								dataKey="label"
								tick={{ fontSize: 10, fill: "#5B6677" }}
								interval="preserveStartEnd"
							/>
							<YAxis tick={{ fontSize: 10, fill: "#5B6677" }} width={34} />
							<Tooltip
								formatter={(v: number) => [fmtInt(v), "half-hours"]}
								labelFormatter={(_, p) => {
									const b = p?.[0]?.payload as HistogramBin | undefined
									return b ? `${fmtSignedMW(b.bin_start_mw)} to ${fmtSignedMW(b.bin_end_mw)}` : ""
								}}
							/>
							<Bar dataKey="count" isAnimationActive={false}>
								{bins.map((b) => (
									<Cell key={b.bin_start_mw} fill={b.mid >= 0 ? "#2A5C9E" : "#9A5B00"} />
								))}
							</Bar>
						</BarChart>
					</ResponsiveContainer>
				</div>
			</div>
			<div className="card p-4">
				<div className="text-sm font-medium">Error over time</div>
				<p className="text-xs text-muted mb-2">Blue = over-forecast, amber = under-forecast</p>
				<div className="h-[220px]" role="img" aria-label="Forecast error over time">
					<ResponsiveContainer>
						<BarChart
							data={over}
							margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
							barCategoryGap={0}
						>
							<CartesianGrid stroke="#E3E1DA" vertical={false} />
							<XAxis
								dataKey="t"
								type="number"
								scale="time"
								domain={["dataMin", "dataMax"]}
								tick={{ fontSize: 10, fill: "#5B6677" }}
								tickFormatter={(t: number) => fmtDay(new Date(t).toISOString())}
								minTickGap={36}
							/>
							<YAxis
								tick={{ fontSize: 10, fill: "#5B6677" }}
								tickFormatter={(v: number) => (v / 1000).toFixed(0)}
								width={34}
							/>
							<ReferenceLine y={0} stroke="#0F1B2D" />
							<Tooltip
								formatter={(v: number) => fmtSignedMW(v)}
								labelFormatter={(t: number) => fmtDateTime(new Date(t).toISOString())}
							/>
							<Bar dataKey="e" isAnimationActive={false}>
								{over.map((d) => (
									<Cell key={d.t} fill={(d.e ?? 0) >= 0 ? "#2A5C9E" : "#9A5B00"} />
								))}
							</Bar>
						</BarChart>
					</ResponsiveContainer>
				</div>
			</div>
			<div className="card p-4">
				<div className="text-sm font-medium">Largest absolute errors</div>
				<p className="text-xs text-muted mb-2">Click a row to inspect its forecast vintages</p>
				<ol className="text-xs tabular-nums divide-y divide-line">
					{topErrors.map((r) => (
						<li key={r.start_time}>
							<button
								className="w-full flex justify-between py-1.5 hover:bg-paper text-left"
								onClick={() => onSelect(r.start_time)}
							>
								<span>{fmtDateTime(r.start_time)}</span>
								<span className="text-muted">
									{fmtMW(r.forecast_mw)} vs {fmtMW(r.actual_mw)}
								</span>
								<span
									className={`font-medium ${(r.error_mw ?? 0) >= 0 ? "text-forecast" : "text-warn"}`}
								>
									{fmtSignedMW(r.error_mw)}
								</span>
							</button>
						</li>
					))}
					{!topErrors.length && (
						<li className="py-4 text-muted">No paired intervals in this range.</li>
					)}
				</ol>
			</div>
		</div>
	)
}
