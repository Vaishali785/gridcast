"""SQLite persistence for retrieved Elexon data (avoids re-fetching on every interaction)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS actuals (
  start_time TEXT NOT NULL, publish_time TEXT NOT NULL,
  settlement_date TEXT, settlement_period INTEGER, generation REAL NOT NULL,
  UNIQUE (start_time, publish_time, generation)
);
CREATE TABLE IF NOT EXISTS forecasts (
  start_time TEXT NOT NULL, publish_time TEXT NOT NULL, generation REAL NOT NULL,
  UNIQUE (start_time, publish_time, generation)
);
CREATE INDEX IF NOT EXISTS idx_forecasts_start ON forecasts (start_time, publish_time);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _iso(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class DataStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ---- writes ------------------------------------------------------------
    def replace_all(self, actuals: pd.DataFrame, forecasts: pd.DataFrame, meta: dict) -> None:
        """Atomically replace stored data (a failed refresh leaves the old data intact)."""
        a = actuals.assign(start_time=_iso(actuals["start_time"]), publish_time=_iso(actuals["publish_time"]))
        f = forecasts.assign(start_time=_iso(forecasts["start_time"]), publish_time=_iso(forecasts["publish_time"]))
        with self._conn() as c:
            c.execute("DELETE FROM actuals")
            c.execute("DELETE FROM forecasts")
            c.executemany(
                "INSERT OR IGNORE INTO actuals VALUES (?,?,?,?,?)",
                [
                    (r.start_time, r.publish_time, None if pd.isna(r.settlement_date) else str(r.settlement_date),
                     None if pd.isna(r.settlement_period) else int(r.settlement_period), float(r.generation))
                    for r in a.itertuples(index=False)
                ],
            )
            c.executemany(
                "INSERT OR IGNORE INTO forecasts VALUES (?,?,?)",
                [(r.start_time, r.publish_time, float(r.generation)) for r in f.itertuples(index=False)],
            )
            c.execute("INSERT OR REPLACE INTO meta VALUES ('refresh', ?)", (json.dumps(meta),))

    # ---- reads -------------------------------------------------------------
    def load_actuals(self) -> pd.DataFrame:
        with self._conn() as c:
            df = pd.read_sql_query("SELECT * FROM actuals", c)
        return _parse(df, ["start_time", "publish_time"])

    def load_forecasts(self) -> pd.DataFrame:
        with self._conn() as c:
            df = pd.read_sql_query("SELECT * FROM forecasts", c)
        return _parse(df, ["start_time", "publish_time"])

    def refresh_meta(self) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT value FROM meta WHERE key='refresh'").fetchone()
        return json.loads(row[0]) if row else None

    def is_empty(self) -> bool:
        return self.refresh_meta() is None


def _parse(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
    return df


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
