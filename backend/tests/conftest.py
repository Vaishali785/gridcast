import pandas as pd
import pytest
from datetime import time

from app.models.domain import CutoffRule


@pytest.fixture
def rule() -> CutoffRule:
    return CutoffRule(time(9, 20), "Europe/London", -1)


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def fc_df(rows):
    """rows: (start, publish, generation)"""
    return pd.DataFrame(
        [{"start_time": ts(a), "publish_time": ts(b), "generation": g} for a, b, g in rows]
    )
