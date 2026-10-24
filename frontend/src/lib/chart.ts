import type { IntervalRow } from "../types/api"

export interface ChartPoint {
	t: number
	forecast: number | null
	actual: number | null
	/** A forecast value with no forecast on either neighbour. A line cannot join it to anything, so it must be drawn as a dot. */
	isolatedForecast: boolean
	row: IntervalRow
}

/** One chart point per half-hour. Missing values stay null (a gap), never 0. */
export function buildChartPoints(series: IntervalRow[]): ChartPoint[] {
	return series.map((r, i) => {
		const prev = series[i - 1]?.forecast_mw ?? null
		const next = series[i + 1]?.forecast_mw ?? null
		return {
			t: Date.parse(r.start_time),
			forecast: r.forecast_mw,
			actual: r.actual_mw,
			isolatedForecast: r.forecast_mw != null && prev == null && next == null,
			row: r,
		}
	})
}

export const hasForecast = (series: IntervalRow[]): boolean =>
	series.some((r) => r.forecast_mw != null)
