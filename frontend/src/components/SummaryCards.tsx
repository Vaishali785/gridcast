import type { Analysis } from "../types/api";
import { fmtInt, fmtMW, fmtMWh, fmtSignedMW } from "../lib/format";

function Card({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className={`card p-4 ${accent ? "border-l-4 border-l-wind" : ""}`}>
      <div className="label">{label}</div>
      <div className="mt-1 font-serif text-2xl tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function SummaryCards({ a }: { a: Analysis }) {
  const { summary: s, metrics: m } = a;
  const bias = m.bias_mw;
  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
      <Card label="Forecast · mean" value={fmtMW(s.forecast_mean_mw)} sub={`peak ${fmtMW(s.forecast_peak_mw)} · ${fmtMWh(s.forecast_energy_mwh)} total`} accent />
      <Card label="Actual · mean" value={fmtMW(s.actual_mean_mw)} sub={`${fmtMWh(s.actual_energy_mwh)} total`} />
      <Card label="MAE" value={fmtMW(m.mae_mw)} sub="mean |forecast − actual|" />
      <Card label="RMSE" value={fmtMW(m.rmse_mw)} sub="penalises large misses" />
      <Card label="Bias" value={fmtSignedMW(bias)} sub={bias == null ? undefined : bias > 0 ? "over-forecast on average" : bias < 0 ? "under-forecast on average" : "no net bias"} />
      <Card label="Valid pairs" value={fmtInt(m.n_pairs)} sub={`of ${fmtInt(s.n_expected_intervals)} half-hours`} />
    </div>
  );
}
