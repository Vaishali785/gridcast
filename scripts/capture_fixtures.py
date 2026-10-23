"""Capture REAL Elexon responses into data/fixtures (run where data.elexon.co.uk is reachable).

Writes fuelhh_sample_2026-01.json / windfor_sample_2026-01.json (same names the fixture loader reads),
so after capture the "fixture" source serves real, offline January 2026 data.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import get_settings  # noqa: E402
from app.services.elexon_client import FIXTURE_ACTUALS, FIXTURE_FORECASTS, ElexonClient  # noqa: E402

s = get_settings()
client = ElexonClient(s)
start = datetime.combine(s.data_start_date, time.min, tzinfo=timezone.utc)
end = datetime.combine(s.data_end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
actuals = client.fetch_actuals(s.data_start_date, s.data_end_date)
forecasts = client.fetch_forecasts(start - timedelta(days=s.forecast_publish_lookback_days), end)
s.fixture_dir.mkdir(parents=True, exist_ok=True)
(s.fixture_dir / FIXTURE_ACTUALS).write_text(json.dumps(actuals))
(s.fixture_dir / FIXTURE_FORECASTS).write_text(json.dumps(forecasts))
print(f"captured {len(actuals)} FUELHH and {len(forecasts)} WINDFOR records")
