import { describe, expect, it } from "vitest"
import type { IntervalRow } from "../types/api"
import { parseError } from "./api"
import { buildChartPoints, hasForecast } from "./chart"
import { fmtMW, fmtMWh, fmtSignedMW, relativeAge } from "./format"
import { prepareRows } from "./table"

const row = (t: string, f: number | null, a: number | null): IntervalRow => ({
	start_time: t,
	settlement_date: "2026-01-10",
	settlement_period: 1,
	forecast_mw: f,
	actual_mw: a,
	error_mw: f != null && a != null ? f - a : null,
	abs_error_mw: f != null && a != null ? Math.abs(f - a) : null,
	forecast_publish_time: null,
	cutoff_time: t,
	lookahead: false,
	n_vintages_eligible: 0,
	actual_publish_time: null,
})

describe("format", () => {
	it("never renders missing values as zero", () => {
		expect(fmtMW(null)).toBe("—")
		expect(fmtMW(0)).toBe("0 MW")
	})
	it("signs errors", () => {
		expect(fmtSignedMW(120)).toBe("+120 MW")
		expect(fmtSignedMW(-120)).toBe("−120 MW")
		expect(fmtSignedMW(0)).toBe("0 MW")
	})
	it("shows energy in GWh", () => expect(fmtMWh(2500)).toBe("2.5 GWh"))
	it("relative age", () => {
		const now = Date.parse("2026-01-01T12:00:00Z")
		expect(relativeAge("2026-01-01T11:30:00Z", now)).toBe("30 min ago")
	})
})

describe("table", () => {
	const rows = [
		row("2026-01-10T00:00:00Z", 100, 90),
		row("2026-01-10T00:30:00Z", null, 50),
		row("2026-01-10T01:00:00Z", 500, 100),
	]
	it("sorts by abs error desc with missing last", () => {
		const out = prepareRows(rows, {
			sortKey: "abs_error_mw",
			sortDir: "desc",
			minAbsError: 0,
			onlyMissing: false,
		})
		expect(out.map((r) => r.abs_error_mw)).toEqual([400, 10, null])
	})
	it("missing last even when ascending", () => {
		const out = prepareRows(rows, {
			sortKey: "abs_error_mw",
			sortDir: "asc",
			minAbsError: 0,
			onlyMissing: false,
		})
		expect(out.map((r) => r.abs_error_mw)).toEqual([10, 400, null])
	})
	it("filters by min error and by missing", () => {
		expect(
			prepareRows(rows, {
				sortKey: "start_time",
				sortDir: "asc",
				minAbsError: 100,
				onlyMissing: false,
			}),
		).toHaveLength(1)
		expect(
			prepareRows(rows, {
				sortKey: "start_time",
				sortDir: "asc",
				minAbsError: 0,
				onlyMissing: true,
			}),
		).toHaveLength(1)
	})
})

describe("api errors", () => {
	it("parses structured backend errors", async () => {
		const res = new Response(
			JSON.stringify({ error: { code: "data_not_loaded", message: "No data", details: {} } }),
			{ status: 409 },
		)
		const e = await parseError(res)
		expect(e.code).toBe("data_not_loaded")
		expect(e.status).toBe(409)
	})
	it("falls back for non-JSON errors", async () => {
		const e = await parseError(new Response("boom", { status: 500 }))
		expect(e.code).toBe("http_error")
	})
})

describe("forecast series for the chart", () => {
	const T = (m: number) => new Date(Date.UTC(2026, 0, 10, 0, m)).toISOString()

	it("hourly forecasts applied to both half-hours form a continuous series (no isolated points)", () => {
		const pts = buildChartPoints([
			row(T(0), 100, 90),
			row(T(30), 100, 95),
			row(T(60), 120, 100),
			row(T(90), 120, 99),
		])
		expect(pts.map((p) => p.forecast)).toEqual([100, 100, 120, 120])
		expect(pts.some((p) => p.isolatedForecast)).toBe(false)
	})

	it("forecast present only on alternate half-hours is flagged isolated so it is drawn as dots, not lost", () => {
		const pts = buildChartPoints([
			row(T(0), 100, 90),
			row(T(30), null, 95),
			row(T(60), 120, 100),
			row(T(90), null, 99),
		])
		expect(pts.map((p) => p.isolatedForecast)).toEqual([true, false, true, false])
	})

	it("keeps missing values as null, never zero", () => {
		const pts = buildChartPoints([row(T(0), null, null)])
		expect(pts[0].forecast).toBeNull()
		expect(pts[0].actual).toBeNull()
	})

	it("detects when a selection has no forecast at all (drives the empty-forecast message)", () => {
		expect(hasForecast([row(T(0), null, 90), row(T(30), null, 95)])).toBe(false)
		expect(hasForecast([row(T(0), null, 90), row(T(30), 5, 95)])).toBe(true)
		expect(hasForecast([row(T(0), 0, 90)])).toBe(true) // a genuine 0 MW forecast still counts
	})
})
