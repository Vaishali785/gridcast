"""Application settings, loaded from environment variables (see .env.example)."""
from __future__ import annotations

from datetime import date, time
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- data source -------------------------------------------------------
    data_source: Literal["live", "fixture"] = "live"
    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = 60.0
    elexon_max_retries: int = 4
    fixture_dir: Path = REPO_ROOT / "data" / "fixtures"
    database_path: Path = REPO_ROOT / "data" / "gridcast.db"
    auto_refresh_on_empty: bool = True

    # --- analysis window (delivery dates, UK local dates) -------------------
    data_start_date: date = date(2026, 1, 1)
    data_end_date: date = date(2026, 1, 31)
    # Forecasts for a delivery day may be published days ahead; fetch this far back.
    forecast_publish_lookback_days: int = 14

    # --- decision cutoff (see README "Decision cutoff") --------------------
    # Default: 09:20 Europe/London on D-1, the EPEX SPOT GB day-ahead gate closure.
    decision_cutoff_local_time: time = time(9, 20)
    decision_cutoff_timezone: str = "Europe/London"
    decision_cutoff_day_offset: int = -1

    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @field_validator("decision_cutoff_day_offset")
    @classmethod
    def _offset_not_positive(cls, v: int) -> int:
        if v > 0:
            raise ValueError("decision_cutoff_day_offset must be <= 0 (cutoff is on or before delivery day)")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
