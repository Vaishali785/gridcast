import type { IntervalRow } from "../types/api";

export type SortKey = "start_time" | "forecast_mw" | "actual_mw" | "error_mw" | "abs_error_mw";
export interface TableOptions { sortKey: SortKey; sortDir: "asc" | "desc"; minAbsError: number; onlyMissing: boolean }

/** Sorts and filters interval rows. Missing (null) values always sort last, regardless of direction. */
export function prepareRows(rows: IntervalRow[], o: TableOptions): IntervalRow[] {
  const filtered = rows.filter((r) => {
    const isMissing = r.forecast_mw == null || r.actual_mw == null;
    if (o.onlyMissing) return isMissing;
    if (o.minAbsError > 0) return r.abs_error_mw != null && r.abs_error_mw >= o.minAbsError;
    return true;
  });
  const dir = o.sortDir === "asc" ? 1 : -1;
  return [...filtered].sort((a, b) => {
    const av = o.sortKey === "start_time" ? Date.parse(a.start_time) : a[o.sortKey];
    const bv = o.sortKey === "start_time" ? Date.parse(b.start_time) : b[o.sortKey];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return (av - bv) * dir;
  });
}
