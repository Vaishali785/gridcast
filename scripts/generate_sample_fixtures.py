"""Generate SAMPLE (synthetic) fixtures in the exact Elexon FUELHH / WINDFOR schemas.

THESE ARE NOT REAL ELEXON DATA. They exist so the app runs when Elexon is unreachable.
Real data: `python scripts/capture_fixtures.py` (needs network access to data.elexon.co.uk).
Deterministic (seeded). Includes realistic edge cases: other fuel types, multiple vintages,
exact duplicates, one conflicting duplicate, missing actuals/forecasts, a null value.
"""
from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "fixtures"
UTC = timezone.utc
Z = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
PUBLISH_HOURS = [(3, 30), (5, 30), (8, 30), (10, 30), (12, 30), (16, 30), (19, 30), (23, 30)]  # 8x/day (docs)

rng = random.Random(2026)
start = datetime(2026, 1, 1, tzinfo=UTC)
n = 31 * 48

# smooth "true" wind process (MW), AR(1) in logit-ish space bounded 300..19000
level, actual = 0.0, []
for i in range(n):
    level = 0.985 * level + rng.gauss(0, 0.12) + 0.05 * math.sin(i / 48 * 2 * math.pi / 5)
    actual.append(max(300.0, min(19000.0, 9000 + 6500 * math.tanh(level))))
actual = [round(a) for a in actual]

missing_actual = set(range(500, 504)) | {1200}          # genuine gaps
zero_actual = {700}                                      # a genuine zero-ish reading
actual[700] = 0

fuelhh, windfor = [], []
for i in range(n):
    t = start + timedelta(minutes=30 * i)
    sp = (i % 48) + 1
    base = {"dataset": "FUELHH", "publishTime": Z(t + timedelta(minutes=35)), "startTime": Z(t),
            "settlementDate": t.strftime("%Y-%m-%d"), "settlementPeriod": sp}
    for fuel, val in (("NUCLEAR", 4044 + rng.randint(-50, 50)), ("CCGT", 8000 + rng.randint(-1500, 1500))):
        fuelhh.append({**base, "fuelType": fuel, "generation": val})
    if i not in missing_actual:
        fuelhh.append({**base, "fuelType": "WIND", "generation": actual[i]})

# forecasts: for each delivery interval, every WINDFOR publication in the 60h before delivery
for i in range(n):
    t = start + timedelta(minutes=30 * i)
    if 800 <= i < 806:
        continue  # forecast gap
    for d in range(-3, 1):
        day = (t + timedelta(days=d)).replace(hour=0, minute=0)
        for h, m in PUBLISH_HOURS:
            pub = day.replace(hour=h, minute=m)
            lead_h = (t - pub).total_seconds() / 3600
            if not (1 <= lead_h <= 60):
                continue
            sigma = 250 + 30 * lead_h                    # error grows with lead time
            fc = max(0, round(actual[i] + rng.gauss(0, sigma) ))
            windfor.append({"dataset": "WINDFOR", "publishTime": Z(pub), "startTime": Z(t), "generation": fc})

windfor.append(dict(windfor[10]))                                           # exact duplicate
conflict = dict(windfor[20]); conflict["generation"] += 250; windfor.append(conflict)  # conflicting duplicate
windfor.append({"dataset": "WINDFOR", "publishTime": Z(start + timedelta(days=5)),
                "startTime": Z(start + timedelta(days=6)), "generation": None})       # null value (invalid)

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "fuelhh_sample_2026-01.json").write_text(json.dumps(fuelhh, separators=(",", ":")))
(OUT / "windfor_sample_2026-01.json").write_text(json.dumps(windfor, separators=(",", ":")))
print(f"fuelhh: {len(fuelhh)} records, windfor: {len(windfor)} records -> {OUT}")
