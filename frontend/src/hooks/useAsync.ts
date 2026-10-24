import { useCallback, useEffect, useRef, useState } from "react"
import { ApiError } from "../lib/api"

export interface AsyncState<T> {
	data: T | null
	error: ApiError | null
	loading: boolean
	reload: () => void
}

/** Runs `fn` whenever `deps` change (or reload() is called). Cancels stale requests. Keeps previous data while refetching. */
export function useAsync<T>(
	fn: ((signal: AbortSignal) => Promise<T>) | null,
	deps: unknown[],
): AsyncState<T> {
	const [data, setData] = useState<T | null>(null)
	const [error, setError] = useState<ApiError | null>(null)
	const [loading, setLoading] = useState<boolean>(fn !== null)
	const [tick, setTick] = useState(0)
	const fnRef = useRef(fn)
	fnRef.current = fn

	useEffect(() => {
		const run = fnRef.current
		if (!run) {
			setLoading(false)
			return
		}
		const ctrl = new AbortController()
		setLoading(true)
		run(ctrl.signal)
			.then((d) => {
				setData(d)
				setError(null)
			})
			.catch((e: unknown) => {
				if ((e as Error).name === "AbortError") return
				setError(e instanceof ApiError ? e : new ApiError((e as Error).message, "unknown", 0))
			})
			.finally(() => {
				if (!ctrl.signal.aborted) setLoading(false)
			})
		return () => ctrl.abort()
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [...deps, tick])

	const reload = useCallback(() => setTick((t) => t + 1), [])
	return { data, error, loading, reload }
}
