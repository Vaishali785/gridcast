"""In-memory snapshot of stored data, reloaded only when a refresh has happened."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import pandas as pd

from app.services.normalize import resolve_actuals, resolve_conflicts
from app.services.store import DataStore


@dataclass(frozen=True)
class Snapshot:
    meta: dict
    actuals: pd.DataFrame          # one row per start_time
    forecasts: pd.DataFrame        # one row per (start_time, publish_time)
    forecasts_raw_count: int


class Repository:
    def __init__(self, store: DataStore) -> None:
        self.store = store
        self._lock = Lock()
        self._snap: Snapshot | None = None

    def snapshot(self) -> Snapshot | None:
        meta = self.store.refresh_meta()
        if meta is None:
            return None
        with self._lock:
            if self._snap is None or self._snap.meta.get("refreshed_at") != meta.get("refreshed_at"):
                raw_f = self.store.load_forecasts()
                forecasts, _ = resolve_conflicts(raw_f, ["start_time", "publish_time"])
                actuals, _ = resolve_actuals(self.store.load_actuals())
                self._snap = Snapshot(meta, actuals, forecasts, len(raw_f))
            return self._snap
