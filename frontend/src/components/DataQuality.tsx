import { fmtDateTimeUtc, fmtInt } from "../lib/format"
import type { Analysis, Metadata } from "../types/api"

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
	return (
		<div className="flex justify-between gap-4 py-1.5 border-b border-line last:border-0">
			<dt className="text-muted">{k}</dt>
			<dd className={`tabular-nums text-right ${warn ? "text-warn font-medium" : ""}`}>{v}</dd>
		</div>
	)
}

export function DataQuality({ meta, analysis }: { meta: Metadata; analysis: Analysis }) {
	const s = analysis.summary
	const rej = (m: Record<string, number> | undefined) =>
		Object.entries(m ?? {})
			.filter(([k]) => k !== "excluded_non_wind_fuel")
			.reduce((a, [, n]) => a + n, 0)
	return (
		<div className="grid md:grid-cols-3 gap-4 text-sm">
			<dl className="card p-4">
				<div className="label mb-2">Retrieved (whole window)</div>
				<Row k="Actual WIND records stored" v={fmtInt(meta.actuals?.stored_records ?? 0)} />
				<Row
					k="Forecast records stored (all vintages)"
					v={fmtInt(meta.forecasts?.stored_records ?? 0)}
				/>
				<Row
					k="Distinct forecast publications"
					v={fmtInt(meta.coverage?.distinct_publish_times ?? 0)}
				/>
				<Row
					k="Records rejected (actual / forecast)"
					v={`${fmtInt(rej(meta.actuals?.rejected))} / ${fmtInt(rej(meta.forecasts?.rejected))}`}
					warn={rej(meta.actuals?.rejected) + rej(meta.forecasts?.rejected) > 0}
				/>
				<Row
					k="Conflicting duplicates resolved"
					v={`${meta.actuals?.conflicting_keys ?? 0} / ${meta.forecasts?.conflicting_keys ?? 0}`}
				/>
			</dl>
			<dl className="card p-4">
				<div className="label mb-2">Selected range</div>
				<Row
					k="Valid paired intervals"
					v={`${fmtInt(analysis.metrics.n_pairs)} of ${fmtInt(s.n_expected_intervals)}`}
				/>
				<Row k="Missing actual" v={fmtInt(s.n_missing_actual)} warn={s.n_missing_actual > 0} />
				<Row
					k="Missing forecast"
					v={fmtInt(s.n_missing_forecast)}
					warn={s.n_missing_forecast > 0}
				/>
				<Row k="Missing both" v={fmtInt(s.n_missing_both)} />
				<Row
					k="Intervals using a post-cutoff forecast"
					v={fmtInt(s.n_lookahead_intervals)}
					warn={s.n_lookahead_intervals > 0}
				/>
				{s.n_forecast_from_hourly > 0 && (
					<Row k="Half-hours using an hourly forecast" v={fmtInt(s.n_forecast_from_hourly)} />
				)}
				<p className="mt-2 text-xs text-muted">
					Missing means unavailable, not zero. Genuine 0 MW readings are kept and counted.
					{s.n_forecast_from_hourly > 0 &&
						" WINDFOR forecasts are hourly: each hourly value is applied to both half-hours of its hour."}
				</p>
			</dl>
			<dl className="card p-4">
				<div className="label mb-2">Provenance &amp; assumptions</div>
				<Row k="Latest successful refresh" v={fmtDateTimeUtc(meta.last_successful_refresh)} />
				<Row
					k="Source"
					v={
						meta.is_sample_data
							? "SAMPLE fixtures (synthetic)"
							: meta.data_source === "live"
								? "Elexon Insights API"
								: "Captured fixtures"
					}
					warn={meta.is_sample_data}
				/>
				<Row k="Decision cutoff" v={meta.cutoff.description} />
				<p className="mt-2 text-xs text-muted">{meta.cutoff.rationale}</p>
			</dl>
		</div>
	)
}
