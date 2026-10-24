const UK = "Europe/London"

/** True minus sign (U+2212) written as an escape so it doesnt get mix with hyphen. */
const MINUS = "\u2212"

export const fmtMW = (v: number | null | undefined, digits = 0): string =>
	v == null
		? "—"
		: `${v.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`

export const fmtSignedMW = (v: number | null | undefined, digits = 0): string =>
	v == null
		? "—"
		: `${v > 0 ? "+" : v < 0 ? MINUS : ""}${Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`

export const fmtMWh = (v: number | null | undefined): string =>
	v == null ? "—" : `${(v / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })} GWh`

export const fmtInt = (v: number): string => v.toLocaleString("en-GB")

/** "10 Jan, 12:00" in UK local time. */
export const fmtDateTime = (iso: string | null | undefined): string =>
	!iso
		? "—"
		: new Date(iso).toLocaleString("en-GB", {
				timeZone: UK,
				day: "2-digit",
				month: "short",
				hour: "2-digit",
				minute: "2-digit",
				hour12: false,
			})

export const fmtDateTimeUtc = (iso: string | null | undefined): string =>
	!iso
		? "—"
		: new Date(iso).toLocaleString("en-GB", {
				timeZone: "UTC",
				day: "2-digit",
				month: "short",
				year: "numeric",
				hour: "2-digit",
				minute: "2-digit",
				hour12: false,
			}) + " UTC"

export const fmtTime = (iso: string): string =>
	new Date(iso).toLocaleTimeString("en-GB", {
		timeZone: UK,
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	})

export const fmtDay = (iso: string): string =>
	new Date(iso).toLocaleDateString("en-GB", { timeZone: UK, day: "2-digit", month: "short" })

export function relativeAge(iso: string, now = Date.now()): string {
	const mins = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000))
	if (mins < 1) return "just now"
	if (mins < 60) return `${mins} min ago`
	const h = Math.round(mins / 60)
	return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`
}
