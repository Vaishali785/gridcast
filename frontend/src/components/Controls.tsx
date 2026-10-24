import { fmtDateTime } from "../lib/format"
import type { Metadata, Mode, VintageTime } from "../types/api"

export interface ControlState {
	start: string
	end: string
	mode: Mode
	asOf: string
}

const MODES: { id: Mode; label: string; hint: string }[] = [
	{
		id: "cutoff",
		label: "Decision-time",
		hint: "Latest forecast published at or before the cutoff",
	},
	{
		id: "latest",
		label: "Retrospective latest",
		hint: "Latest forecast before delivery — NOT known at decision time",
	},
	{
		id: "vintage",
		label: "Pick a vintage",
		hint: "Latest forecast published at or before a time you choose",
	},
]

interface Props {
	meta: Metadata
	value: ControlState
	vintages: VintageTime[]
	onChange: (v: ControlState) => void
}

export function Controls({ meta, value, vintages, onChange }: Props) {
	const set = (patch: Partial<ControlState>) => onChange({ ...value, ...patch })
	const setMode = (mode: Mode) =>
		set({
			mode,
			asOf:
				mode === "vintage" && !value.asOf
					? (vintages[vintages.length - 1]?.publish_time ?? "")
					: value.asOf,
		})
	const input = "border border-line rounded px-2 py-1 text-sm bg-surface"
	return (
		<div
			className="flex flex-wrap items-baseline gap-x-8 gap-y-4 "
			role="group"
			aria-label="Analysis controls"
		>
			<div>
				<div className="label mb-1">Delivery dates (UK)</div>
				<div className="flex items-center gap-2">
					<input
						aria-label="Start date"
						type="date"
						className={input}
						min={meta.window_start}
						max={value.end}
						value={value.start}
						onChange={(e) => e.target.value && set({ start: e.target.value })}
					/>
					<span className="text-muted">to</span>
					<input
						aria-label="End date"
						type="date"
						className={input}
						min={value.start}
						max={meta.window_end}
						value={value.end}
						onChange={(e) => e.target.value && set({ end: e.target.value })}
					/>
				</div>
				<div className="mt-1.5 flex gap-2 text-xs">
					<button
						className="underline text-muted hover:text-ink"
						onClick={() => set({ start: meta.window_start, end: meta.window_end })}
					>
						Full month
					</button>
					<button
						className="underline text-muted hover:text-ink"
						onClick={() => set({ end: value.start })}
					>
						Single day
					</button>
				</div>
			</div>
			<div>
				<div className="label mb-1">Forecast selection</div>
				<div
					className="inline-flex rounded border border-line overflow-hidden"
					role="radiogroup"
					aria-label="Forecast selection mode"
				>
					{MODES.map((m) => (
						<button
							key={m.id}
							role="radio"
							aria-checked={value.mode === m.id}
							title={m.hint}
							onClick={() => setMode(m.id)}
							className={`px-3 py-1.5 text-sm border-r border-line last:border-r-0 ${value.mode === m.id ? (m.id === "cutoff" ? "bg-wind text-white" : "bg-warn text-white") : "bg-surface hover:bg-paper"}`}
						>
							{m.label}
						</button>
					))}
				</div>
			</div>
			{value.mode === "vintage" && (
				<div>
					<label className="label mb-1 block" htmlFor="vintage">
						Forecasts published up to
					</label>
					<select
						id="vintage"
						className={input}
						value={value.asOf}
						onChange={(e) => set({ asOf: e.target.value })}
					>
						{vintages.map((v) => (
							<option key={v.publish_time} value={v.publish_time}>
								{fmtDateTime(v.publish_time)} ({v.intervals_covered} intervals)
							</option>
						))}
					</select>
				</div>
			)}
			{/* <div className="ml-auto text-xs text-muted max-w-xs">
				<span className="label block">Decision cutoff assumption</span>
				{meta.cutoff.description}
			</div> */}
		</div>
	)
}
