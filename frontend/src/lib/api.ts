import type {
	Analysis,
	ApiErrorBody,
	Metadata,
	Mode,
	VintageEvolution,
	VintageTimes,
} from "../types/api"

const BASE = import.meta.env.VITE_API_BASE_URL ?? ""

export class ApiError extends Error {
	constructor(
		message: string,
		public code: string,
		public status: number,
	) {
		super(message)
	}
}

export async function parseError(res: Response): Promise<ApiError> {
	try {
		const body = (await res.json()) as ApiErrorBody
		return new ApiError(body.error.message, body.error.code, res.status)
	} catch {
		return new ApiError(`Request failed (HTTP ${res.status})`, "http_error", res.status)
	}
}

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
	let res: Response
	try {
		res = await fetch(`${BASE}${path}`, { ...init, signal })
	} catch (e) {
		if ((e as Error).name === "AbortError") throw e
		throw new ApiError("Cannot reach the GridCast API. Is the backend running?", "network_error", 0)
	}
	if (!res.ok) throw await parseError(res)
	return res.json() as Promise<T>
}

export interface AnalysisParams {
	start: string
	end: string
	mode: Mode
	asOf?: string
}

export const api = {
	metadata: (s?: AbortSignal) => request<Metadata>("/api/metadata", undefined, s),
	analysis: (p: AnalysisParams, s?: AbortSignal) => {
		const q = new URLSearchParams({ start_date: p.start, end_date: p.end, mode: p.mode })
		if (p.mode === "vintage" && p.asOf) q.set("as_of", p.asOf)
		return request<Analysis>(`/api/wind/analysis?${q}`, undefined, s)
	},
	vintageTimes: (start: string, end: string, s?: AbortSignal) =>
		request<VintageTimes>(
			`/api/wind/vintage-times?start_date=${start}&end_date=${end}`,
			undefined,
			s,
		),
	vintages: (startTime: string, s?: AbortSignal) =>
		request<VintageEvolution>(
			`/api/wind/vintages?start_time=${encodeURIComponent(startTime)}`,
			undefined,
			s,
		),
	refresh: (source?: "live" | "fixture") =>
		request<unknown>("/api/data/refresh", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ source: source ?? null }),
		}),
}
