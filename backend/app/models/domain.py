"""Domain types shared by services (framework-independent)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum
from zoneinfo import ZoneInfo


class SelectionMode(str, Enum):
    CUTOFF = "cutoff"      # forecast actually available at the decision cutoff
    LATEST = "latest"      # latest published forecast (retrospective)
    VINTAGE = "vintage"    # latest forecast published at or before a user-chosen time


@dataclass(frozen=True)
class CutoffRule:
    """Decision cutoff for a delivery interval: `local_time` on (delivery date + day_offset)."""

    local_time: time
    timezone: str
    day_offset: int = -1

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def describe(self) -> str:
        day = "D" if self.day_offset == 0 else f"D{self.day_offset:+d}"
        return f"{self.local_time.strftime('%H:%M')} {self.timezone} on {day} (D = delivery date)"


@dataclass(frozen=True)
class IngestReport:
    raw_records: int
    valid_records: int
    rejected: dict[str, int]
    exact_duplicates_dropped: int
