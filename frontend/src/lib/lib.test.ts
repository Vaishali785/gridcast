import { describe, expect, it } from "vitest";
import { parseError } from "./api";
import { fmtMW, fmtMWh, fmtSignedMW, relativeAge } from "./format";
import { prepareRows } from "./table";
import type { IntervalRow } from "../types/api";

const row = (t: string, f: number | null, a: number | null): IntervalRow => ({
  start_time: t, settlement_date: "2026-01-10", settlement_period: 1, forecast_mw: f, actual_mw: a,
  error_mw: f != null && a != null ? f - a : null, abs_error_mw: f != null && a != null ? Math.abs(f - a) : null,
  forecast_publish_time: null, cutoff_time: t, lookahead: false, n_vintages_eligible: 0, actual_publish_time: null,
});

describe("format", () => {
  it("never renders missing values as zero", () => {
    expect(fmtMW(null)).toBe("—");
    expect(fmtMW(0)).toBe("0 MW");
  });
  it("signs errors", () => {
    expect(fmtSignedMW(120)).toBe("+120 MW");
    expect(fmtSignedMW(-120)).toBe("−120 MW");
    expect(fmtSignedMW(0)).toBe("0 MW");
  });
  it("shows energy in GWh", () => expect(fmtMWh(2500)).toBe("2.5 GWh"));
  it("relative age", () => {
    const now = Date.parse("2026-01-01T12:00:00Z");
    expect(relativeAge("2026-01-01T11:30:00Z", now)).toBe("30 min ago");
  });
});

describe("table", () => {
  const rows = [row("2026-01-10T00:00:00Z", 100, 90), row("2026-01-10T00:30:00Z", null, 50), row("2026-01-10T01:00:00Z", 500, 100)];
  it("sorts by abs error desc with missing last", () => {
    const out = prepareRows(rows, { sortKey: "abs_error_mw", sortDir: "desc", minAbsError: 0, onlyMissing: false });
    expect(out.map((r) => r.abs_error_mw)).toEqual([400, 10, null]);
  });
  it("missing last even when ascending", () => {
    const out = prepareRows(rows, { sortKey: "abs_error_mw", sortDir: "asc", minAbsError: 0, onlyMissing: false });
    expect(out.map((r) => r.abs_error_mw)).toEqual([10, 400, null]);
  });
  it("filters by min error and by missing", () => {
    expect(prepareRows(rows, { sortKey: "start_time", sortDir: "asc", minAbsError: 100, onlyMissing: false })).toHaveLength(1);
    expect(prepareRows(rows, { sortKey: "start_time", sortDir: "asc", minAbsError: 0, onlyMissing: true })).toHaveLength(1);
  });
});

describe("api errors", () => {
  it("parses structured backend errors", async () => {
    const res = new Response(JSON.stringify({ error: { code: "data_not_loaded", message: "No data", details: {} } }), { status: 409 });
    const e = await parseError(res);
    expect(e.code).toBe("data_not_loaded");
    expect(e.status).toBe(409);
  });
  it("falls back for non-JSON errors", async () => {
    const e = await parseError(new Response("boom", { status: 500 }));
    expect(e.code).toBe("http_error");
  });
});
