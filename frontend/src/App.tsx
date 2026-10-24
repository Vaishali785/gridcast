import { useState } from "react"
import Footer from "./components/Footer"
import { Header } from "./components/Header"
import { EmptyState, ErrorBox, Skeleton } from "./components/States"
import { useAsync } from "./hooks/useAsync"
import { ApiError, api } from "./lib/api"
import { Dashboard } from "./pages/Dashboard"

export default function App() {
	const meta = useAsync((s) => api.metadata(s), [])
	const [refreshing, setRefreshing] = useState(false)
	const [refreshError, setRefreshError] = useState<ApiError | null>(null)

	const refresh = async () => {
		setRefreshing(true)
		setRefreshError(null)
		try {
			await api.refresh()
			meta.reload()
		} catch (e) {
			setRefreshError(e instanceof ApiError ? e : new ApiError(String(e), "unknown", 0))
		} finally {
			setRefreshing(false)
		}
	}

	const m = meta.data
	return (
		<>
			<Header meta={m} refreshing={refreshing} onRefresh={refresh} />
			<main className="max-w-[1280px] mx-auto px-6 py-8">
				{refreshError && (
					<div className="mb-6">
						<ErrorBox error={refreshError} />
						<p className="text-xs text-muted mt-2">
							Previously loaded data (if any) has been kept.
						</p>
					</div>
				)}
				{meta.error ? (
					<ErrorBox error={meta.error} onRetry={meta.reload} />
				) : !m ? (
					<div className="space-y-4">
						<Skeleton className="h-24" />
						<Skeleton className="h-96" />
					</div>
				) : !m.data_loaded ? (
					<EmptyState title="No data loaded yet">
						<p>
							GridCast hasn't retrieved January 2026 wind data. Use “Refresh data” to fetch it from{" "}
							{m.data_source === "live" ? "the Elexon Insights API" : "the sample fixtures"}.
						</p>
						<button className="btn btn-primary mt-4" onClick={refresh} disabled={refreshing}>
							{refreshing ? "Loading…" : "Load data"}
						</button>
					</EmptyState>
				) : (
					<Dashboard meta={m} />
				)}
			</main>
			<Footer />
		</>
	)
}
