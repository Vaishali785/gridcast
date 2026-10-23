"""Request/response schemas (rendered in the OpenAPI docs at /docs)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"]
    data_loaded: bool


class CutoffAssumption(BaseModel):
    description: str
    local_time: str = Field(examples=["09:20"])
    timezone: str
    day_offset: int
    rationale: str


class IngestStats(BaseModel):
    raw_records: int
    stored_records: int
    rejected: dict[str, int]
    exact_duplicates_dropped: int
    conflicting_keys: int


class Coverage(BaseModel):
    expected_intervals: int
    actual_intervals: int
    forecast_intervals: int
    first_publish_time: datetime | None
    last_publish_time: datetime | None
    distinct_publish_times: int


class MetadataResponse(BaseModel):
    data_loaded: bool
    data_source: Literal["live", "fixture"]
    is_sample_data: bool = Field(description="True when the data comes from labelled sample fixtures.")
    last_successful_refresh: datetime | None
    window_start: date
    window_end: date
    cutoff: CutoffAssumption
    actuals: IngestStats | None = None
    forecasts: IngestStats | None = None
    coverage: Coverage | None = None


class IntervalRow(BaseModel):
    start_time: datetime
    settlement_date: str
    settlement_period: int
    forecast_mw: float | None
    actual_mw: float | None
    error_mw: float | None = Field(description="forecast - actual (MW). Positive = over-forecast.")
    abs_error_mw: float | None
    forecast_publish_time: datetime | None
    cutoff_time: datetime
    lookahead: bool = Field(description="True if the selected forecast was published AFTER this interval's decision cutoff.")
    n_vintages_eligible: int
    actual_publish_time: datetime | None


class Summary(BaseModel):
    n_expected_intervals: int
    n_forecast_available: int
    n_actual_available: int
    n_missing_forecast: int
    n_missing_actual: int
    n_missing_both: int
    n_lookahead_intervals: int
    forecast_mean_mw: float | None
    forecast_peak_mw: float | None
    actual_mean_mw: float | None
    forecast_energy_mwh: float | None
    actual_energy_mwh: float | None
    paired_forecast_energy_mwh: float | None
    paired_actual_energy_mwh: float | None


class MetricsOut(BaseModel):
    n_pairs: int
    mae_mw: float | None
    rmse_mw: float | None
    bias_mw: float | None
    bias_convention: str = "error = forecast - actual; bias > 0 means the forecast over-predicted wind."


class HistogramBin(BaseModel):
    bin_start_mw: float
    bin_end_mw: float
    count: int


class AnalysisResponse(BaseModel):
    start_date: date
    end_date: date
    mode: Literal["cutoff", "latest", "vintage"]
    mode_label: str
    is_retrospective: bool = Field(description="True when any selected forecast was published after its decision cutoff.")
    as_of: datetime | None
    cutoff: CutoffAssumption
    is_sample_data: bool
    last_successful_refresh: datetime
    summary: Summary
    metrics: MetricsOut
    series: list[IntervalRow]
    top_errors: list[IntervalRow]
    error_histogram: list[HistogramBin]


class ForecastRecord(BaseModel):
    start_time: datetime
    publish_time: datetime
    generation_mw: float
    available_at_cutoff: bool


class ForecastsResponse(BaseModel):
    count: int
    truncated: bool
    records: list[ForecastRecord]


class ActualRecord(BaseModel):
    start_time: datetime
    publish_time: datetime
    settlement_date: str | None
    settlement_period: int | None
    generation_mw: float


class ActualsResponse(BaseModel):
    count: int
    records: list[ActualRecord]


class VintageEntry(BaseModel):
    publish_time: datetime
    forecast_mw: float
    available_at_cutoff: bool
    hours_before_delivery: float


class VintageEvolution(BaseModel):
    start_time: datetime
    cutoff_time: datetime
    actual_mw: float | None
    vintages: list[VintageEntry]


class VintageTime(BaseModel):
    publish_time: datetime
    intervals_covered: int


class VintageTimesResponse(BaseModel):
    start_date: date
    end_date: date
    vintage_times: list[VintageTime]


class RefreshRequest(BaseModel):
    source: Literal["live", "fixture"] | None = Field(default=None, description="Defaults to DATA_SOURCE.")


class RefreshResponse(BaseModel):
    refreshed_at: datetime
    source: Literal["live", "fixture"]
    is_sample: bool
    actuals: IngestStats
    forecasts: IngestStats
