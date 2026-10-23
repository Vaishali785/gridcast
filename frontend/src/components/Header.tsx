import type { Metadata } from "../types/api";
import { fmtDateTimeUtc, relativeAge } from "../lib/format";

const NAV = [["overview", "Overview"], ["forecast", "Forecast vs actual"], ["vintages", "Vintages"], ["errors", "Errors"], ["quality", "Data quality"]];

export function Header({ meta, refreshing, onRefresh }: { meta: Metadata | null; refreshing: boolean; onRefresh: () => void }) {
  return (
    <header className="sticky top-0 z-20 bg-paper/95 backdrop-blur border-b border-line">
      <div className="max-w-[1280px] mx-auto px-6 h-14 flex items-center gap-6">
        <a href="#overview" className="flex items-center gap-2 font-serif text-lg font-semibold">
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden><rect width="32" height="32" rx="7" fill="#0F1B2D" /><path d="M6 20c4-8 7-8 10 0s6 8 10 0" stroke="#38B27F" strokeWidth="3" fill="none" strokeLinecap="round" /></svg>
          GridCast
        </a>
        <nav className="hidden md:flex gap-4 text-sm text-muted" aria-label="Sections">
          {NAV.map(([id, label]) => <a key={id} href={`#${id}`} className="hover:text-ink">{label}</a>)}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs text-muted">
          {meta?.is_sample_data && <span className="px-2 py-0.5 rounded bg-warnsoft text-warn font-medium">SAMPLE DATA</span>}
          {meta?.last_successful_refresh && (
            <span title={fmtDateTimeUtc(meta.last_successful_refresh)}>
              Data refreshed {relativeAge(meta.last_successful_refresh)} · {meta.data_source}
            </span>
          )}
          <button className="btn" onClick={onRefresh} disabled={refreshing}>{refreshing ? "Refreshing…" : "Refresh data"}</button>
        </div>
      </div>
    </header>
  );
}
