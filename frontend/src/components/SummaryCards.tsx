import { fmtMW, fmtSignedMW } from "../lib/format"
import type { Analysis } from "../types/api"

function Card({ label, value, sub }: { label: string; value: string; sub?: string }) {
	return (
		<div className="card p-4 h-full">
			<div className="label">{label}</div>
			<div className="mt-1 font-sans text-3xl tabular-nums tracking-[-3px]">{value}</div>
			<div className="mt-0.5 text-xs text-muted min-h-[1rem]">{sub}</div>
		</div>
	)
}

export function SummaryCards({ a }: { a: Analysis }) {
	const { metrics: m } = a
	const bias = m.bias_mw
	return (
		<div className="grid grid-cols-1 sm:grid-cols-3 gap-3 ">
			<Card label="MAE (Mean Absolute Error)" value={fmtMW(m.mae_mw)} />
			<Card label="RMSE (Root Mean Square Error) " value={fmtMW(m.rmse_mw)} />
			<Card
				label="Bias"
				value={fmtSignedMW(bias)}
				sub={
					bias == null
						? undefined
						: bias > 0
							? "over-forecast"
							: bias < 0
								? "under-forecast"
								: undefined
				}
			/>
		</div>
	)
}
