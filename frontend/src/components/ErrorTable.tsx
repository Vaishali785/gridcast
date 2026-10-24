import { useMemo, useState } from "react"
import { fmtDateTime, fmtInt, fmtMW, fmtSignedMW } from "../lib/format"
import { prepareRows, type SortKey, type TableOptions } from "../lib/table"
import type { IntervalRow } from "../types/api"

const PAGE = 48
const COLS: { key: SortKey; label: string; right?: boolean }[] = [
	{ key: "start_time", label: "Delivery (UK)" },
	{ key: "forecast_mw", label: "Forecast", right: true },
	{ key: "actual_mw", label: "Actual", right: true },
	{ key: "error_mw", label: "Error (F-A)", right: true },
	{ key: "abs_error_mw", label: "|Error|", right: true },
]

export function ErrorTable({
	rows,
	onSelect,
	selected,
}: {
	rows: IntervalRow[]
	onSelect: (iso: string) => void
	selected: string | null
}) {
	const [opts, setOpts] = useState<TableOptions>({
		sortKey: "start_time",
		sortDir: "asc",
		minAbsError: 0,
		onlyMissing: false,
	})
	const [page, setPage] = useState(0)
	const view = useMemo(() => prepareRows(rows, opts), [rows, opts])
	const pages = Math.max(1, Math.ceil(view.length / PAGE))
	const cur = Math.min(page, pages - 1)
	const slice = view.slice(cur * PAGE, cur * PAGE + PAGE)
	const update = (p: Partial<TableOptions>) => {
		setOpts({ ...opts, ...p })
		setPage(0)
	}
	const sortBy = (key: SortKey) =>
		update({
			sortKey: key,
			sortDir: opts.sortKey === key && opts.sortDir === "desc" ? "asc" : "desc",
		})

	return (
		<div className="card">
			<div className="p-3 flex flex-wrap items-center gap-4 border-b border-line text-sm">
				<label className="flex items-center gap-2">
					Min |error| (MW)
					<input
						type="number"
						min={0}
						step={100}
						value={opts.minAbsError}
						disabled={opts.onlyMissing}
						onChange={(e) => update({ minAbsError: Math.max(0, Number(e.target.value) || 0) })}
						className="w-24 border border-line rounded px-2 py-1"
					/>
				</label>
				<label className="flex items-center gap-2">
					<input
						type="checkbox"
						checked={opts.onlyMissing}
						onChange={(e) => update({ onlyMissing: e.target.checked })}
					/>{" "}
					Only intervals with missing data
				</label>
				<span className="ml-auto text-xs text-muted">
					{fmtInt(view.length)} of {fmtInt(rows.length)} half-hours
				</span>
			</div>
			<div className="overflow-auto max-h-[520px]">
				<table className="w-full text-xs tabular-nums">
					<thead className="sticky top-0 bg-surface text-left text-muted shadow-[0_1px_0_#E3E1DA]">
						<tr>
							{COLS.map((c) => (
								<th
									key={c.key}
									className={`p-2 font-medium ${c.right ? "text-right" : ""}`}
									aria-sort={
										opts.sortKey === c.key
											? opts.sortDir === "asc"
												? "ascending"
												: "descending"
											: "none"
									}
								>
									<button onClick={() => sortBy(c.key)} className="hover:text-ink">
										{c.label}
										{opts.sortKey === c.key ? (opts.sortDir === "asc" ? " ▲" : " ▼") : ""}
									</button>
								</th>
							))}
							<th className="p-2 font-medium">Forecast published</th>
							<th className="p-2 font-medium">Notes</th>
						</tr>
					</thead>
					<tbody>
						{slice.map((r) => (
							<tr
								key={r.start_time}
								onClick={() => onSelect(r.start_time)}
								className={`border-t border-line cursor-pointer hover:bg-paper ${selected === r.start_time ? "bg-wind-soft" : ""}`}
							>
								<td className="p-2">
									{fmtDateTime(r.start_time)}{" "}
									<span className="text-muted">SP{r.settlement_period}</span>
								</td>
								<td className="p-2 text-right">
									{r.forecast_mw == null ? (
										<span className="text-muted">unavailable</span>
									) : (
										fmtMW(r.forecast_mw)
									)}
								</td>
								<td className="p-2 text-right">
									{r.actual_mw == null ? (
										<span className="text-muted">unavailable</span>
									) : (
										fmtMW(r.actual_mw)
									)}
								</td>
								<td className="p-2 text-right">{fmtSignedMW(r.error_mw)}</td>
								<td className="p-2 text-right">{fmtMW(r.abs_error_mw)}</td>
								<td className="p-2">{fmtDateTime(r.forecast_publish_time)}</td>
								<td className="p-2 text-warn">{r.lookahead ? "post-cutoff forecast" : ""}</td>
							</tr>
						))}
						{!slice.length && (
							<tr>
								<td colSpan={7} className="p-6 text-center text-muted">
									No half-hours match these filters.
								</td>
							</tr>
						)}
					</tbody>
				</table>
			</div>
			<div className="p-2 flex items-center justify-end gap-2 text-xs border-t border-line">
				<button className="btn" disabled={cur === 0} onClick={() => setPage(cur - 1)}>
					Prev
				</button>
				<span>
					Page {cur + 1} / {pages}
				</span>
				<button className="btn" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>
					Next
				</button>
			</div>
		</div>
	)
}
