import { useEffect, useMemo, useState } from "react"
import { Controls, type ControlState } from "../components/Controls"
import { DataQuality } from "../components/DataQuality"
import { ErrorAnalysis } from "../components/ErrorAnalysis"
import { ErrorTable } from "../components/ErrorTable"
import { ForecastChart } from "../components/ForecastChart"
import { ErrorBox, Section, Skeleton } from "../components/States"
import { SummaryCards } from "../components/SummaryCards"
import { VintagePanel } from "../components/VintagePanel"
import { useAsync } from "../hooks/useAsync"
import { api } from "../lib/api"
import { fmtDateTime } from "../lib/format"
import type { Metadata } from "../types/api"

type DetailId = "vintages" | "errors" | "quality"

export function Dashboard({ meta }: { meta: Metadata }) {
	const [ctl, setCtl] = useState<ControlState>({
		start: meta.window_start,
		end: meta.window_end,
		mode: "cutoff",
		asOf: "",
	})
	const [selected, setSelected] = useState<string | null>(null)

	const vt = useAsync(
		(s) => api.vintageTimes(ctl.start, ctl.end, s),
		[ctl.start, ctl.end, meta.last_successful_refresh],
	)
	const vintages = vt.data?.vintage_times ?? []
	// keep a valid vintage selected when the range changes
	useEffect(() => {
		if (
			ctl.mode === "vintage" &&
			vintages.length &&
			!vintages.some((v) => v.publish_time === ctl.asOf)
		)
			setCtl((c) => ({ ...c, asOf: vintages[vintages.length - 1].publish_time }))
	}, [vintages, ctl.mode, ctl.asOf])

	const ready = ctl.mode !== "vintage" || !!ctl.asOf
	const an = useAsync(
		ready
			? (s) => api.analysis({ start: ctl.start, end: ctl.end, mode: ctl.mode, asOf: ctl.asOf }, s)
			: null,
		[ctl.start, ctl.end, ctl.mode, ctl.asOf, ready, meta.last_successful_refresh],
	)
	const a = an.data

	const firstPair = useMemo(
		() => a?.series.find((r) => r.forecast_mw != null && r.actual_mw != null)?.start_time ?? null,
		[a],
	)
	useEffect(() => {
		if (!selected && firstPair) setSelected(firstPair)
	}, [selected, firstPair])
	// Detailed sections are collapsed by default; nav links (#vintages etc.) and row clicks open them.
	const [open, setOpen] = useState<Record<DetailId, boolean>>({
		vintages: false,
		errors: false,
		quality: false,
	})
	const toggle = (id: DetailId) => setOpen((o) => ({ ...o, [id]: !o[id] }))
	useEffect(() => {
		const openFromHash = () => {
			const id = window.location.hash.slice(1) as DetailId
			if (id in open) setOpen((o) => ({ ...o, [id]: true }))
		}
		openFromHash()
		window.addEventListener("hashchange", openFromHash)
		return () => window.removeEventListener("hashchange", openFromHash)
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [])
	const select = (iso: string) => {
		setSelected(iso)
		setOpen((o) => ({ ...o, vintages: true }))
		setTimeout(
			() => document.getElementById("vintages")?.scrollIntoView({ behavior: "smooth" }),
			50,
		)
	}

	const missing = a ? a.summary.n_expected_intervals - a.metrics.n_pairs : null

	return (
		<div className="space-y-8">
			<Section id="overview" title="Wind forecast accuracy">
				<div className="hello card p-5 bg-surface/70 ">
					<Controls meta={meta} value={ctl} vintages={vintages} onChange={setCtl} />
					{a && a.is_retrospective && (
						<div
							role="status"
							className="mt-4 rounded border border-warn/40 bg-warnsoft text-warn px-4 py-2.5 text-sm"
						>
							<strong>Retrospective view.</strong>{" "}
							{a.summary.n_lookahead_intervals.toLocaleString("en-GB")} half-hours use a forecast
							published after the decision cutoff
							{a.mode === "vintage" && a.as_of ? ` (up to ${fmtDateTime(a.as_of)})` : ""}, so
							accuracy is overstated versus decision time.
						</div>
					)}
					<div
						className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted justify-between border-t-[1px] border-t-line pt-2"
						aria-label="Data status"
					>
						<div className=" text-xs text-muted flex flex-col items-start">
							<span className="label block">Decision cutoff assumption: </span>
							{meta.cutoff.description}
						</div>
						<div className="flex gap-6">
							<span className="inline-flex items-center gap-1.5">
								<span
									aria-hidden
									className={`inline-block w-2 h-2 rounded-full ${meta.is_sample_data ? "bg-warn" : "bg-wind"}`}
								/>
								{meta.is_sample_data ? "Sample data" : "Live data"}
							</span>
							<span
								title={
									a
										? `${a.summary.n_missing_actual} missing actual · ${a.summary.n_missing_forecast} missing forecast`
										: undefined
								}
							>
								{missing == null
									? "—"
									: `${missing.toLocaleString("en-GB")} half-hour${missing === 1 ? "" : "s"} missing data`}
							</span>
						</div>
					</div>
				</div>

				<div className={`mt-5 ${an.loading && a ? "opacity-60" : ""}`}>
					{an.error ? (
						<ErrorBox error={an.error} onRetry={an.reload} />
					) : !a ? (
						<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-3xl">
							{Array.from({ length: 3 }, (_, i) => (
								<Skeleton key={i} className="h-24" />
							))}
						</div>
					) : (
						<SummaryCards a={a} />
					)}
				</div>
				<div id="forecast" className="mt-6 scroll-mt-20">
					{a ? (
						<ForecastChart series={a.series} selected={selected} onSelect={setSelected} />
					) : (
						<Skeleton className="h-[420px]" />
					)}
				</div>
			</Section>

			<Section
				id="vintages"
				title="Forecast vintages"
				subtitle="Hollow points were published after the decision cutoff."
				open={open.vintages}
				onToggle={() => toggle("vintages")}
			>
				<VintagePanel startTime={selected} />
			</Section>

			<Section
				id="errors"
				title="Error analysis"
				subtitle="Error = forecast − actual; positive means over-forecast."
				open={open.errors}
				onToggle={() => toggle("errors")}
			>
				{a ? (
					<div className="space-y-4">
						<ErrorAnalysis
							histogram={a.error_histogram}
							series={a.series}
							topErrors={a.top_errors}
							onSelect={select}
						/>
						<ErrorTable rows={a.series} selected={selected} onSelect={select} />
					</div>
				) : (
					<Skeleton className="h-96" />
				)}
			</Section>

			<Section
				id="quality"
				title="Data quality &amp; assumptions"
				open={open.quality}
				onToggle={() => toggle("quality")}
			>
				{a ? <DataQuality meta={meta} analysis={a} /> : <Skeleton className="h-40" />}
			</Section>
		</div>
	)
}
