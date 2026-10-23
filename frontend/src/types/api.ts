// Mirrors backend/app/schemas/api.py
export type Mode = "cutoff" | "latest" | "vintage";

export interface CutoffAssumption { description: string; local_time: string; timezone: string; day_offset: number; rationale: string }
export interface IngestStats { raw_records: number; stored_records: number; rejected: Record<string, number>; exact_duplicates_dropped: number; conflicting_keys: number }
export interface Coverage { expected_intervals: number; actual_intervals: number; forecast_intervals: number; first_publish_time: string | null; last_publish_time: string | null; distinct_publish_times: number }
export interface Metadata {
  data_loaded: boolean; data_source: "live" | "fixture"; is_sample_data: boolean; last_successful_refresh: string | null;
  window_start: string; window_end: string; cutoff: CutoffAssumption;
  actuals: IngestStats | null; forecasts: IngestStats | null; coverage: Coverage | null;
}
export interface IntervalRow {
  start_time: string; settlement_date: string; settlement_period: number;
  forecast_mw: number | null; actual_mw: number | null; error_mw: number | null; abs_error_mw: number | null;
  forecast_publish_time: string | null; cutoff_time: string; lookahead: boolean; n_vintages_eligible: number;
  actual_publish_time: string | null;
}
export interface Summary {
  n_expected_intervals: number; n_forecast_available: number; n_actual_available: number;
  n_missing_forecast: number; n_missing_actual: number; n_missing_both: number; n_lookahead_intervals: number;
  forecast_mean_mw: number | null; forecast_peak_mw: number | null; actual_mean_mw: number | null;
  forecast_energy_mwh: number | null; actual_energy_mwh: number | null;
  paired_forecast_energy_mwh: number | null; paired_actual_energy_mwh: number | null;
}
export interface MetricsOut { n_pairs: number; mae_mw: number | null; rmse_mw: number | null; bias_mw: number | null; bias_convention: string }
export interface HistogramBin { bin_start_mw: number; bin_end_mw: number; count: number }
export interface Analysis {
  start_date: string; end_date: string; mode: Mode; mode_label: string; is_retrospective: boolean; as_of: string | null;
  cutoff: CutoffAssumption; is_sample_data: boolean; last_successful_refresh: string;
  summary: Summary; metrics: MetricsOut; series: IntervalRow[]; top_errors: IntervalRow[]; error_histogram: HistogramBin[];
}
export interface VintageTime { publish_time: string; intervals_covered: number }
export interface VintageTimes { vintage_times: VintageTime[] }
export interface VintageEntry { publish_time: string; forecast_mw: number; available_at_cutoff: boolean; hours_before_delivery: number }
export interface VintageEvolution { start_time: string; cutoff_time: string; actual_mw: number | null; vintages: VintageEntry[] }
export interface ApiErrorBody { error: { code: string; message: string; details: Record<string, unknown> } }
