# GridCast — UK wind forecast intelligence

A wind-generation forecast analytics dashboard for a UK electricity procurement team. It shows the wind forecast that was **actually available when day-ahead purchasing decisions are made**, and measures its accuracy against actual wind generation, using Elexon BMRS data for **January 2026** delivery dates.

> **Status / honesty notes** (read before relying on any number)
>
> - **Deployed URL:** _none — not deployed yet._ Deployment instructions are below; this README will get the URL once a deployment actually exists.
> - The build environment had **no network access to Elexon**, so the live retrieval path has been unit-tested against mocked HTTP but **not run against the real API**. The app ships with clearly labelled **SAMPLE (synthetic) fixtures** so everything can be run offline. Every sample-data view carries a "SAMPLE DATA" badge. See [Known limitations](#known-limitations).
> - Docker files are provided but were **not built/run** in the build environment (no Docker daemon). The backend (42 tests), frontend (9 tests), type-check, production build and a headless-browser smoke test were run.

## Target users & purpose

Analysts on a procurement desk buying from the GB day-ahead wholesale market. Questions it answers: _What wind did we expect when we bought? What did we get? How wrong were we, in which direction, and when?_

## Features

- **Decision-time forecast selection** — for every half-hour, the latest WINDFOR forecast with `publishTime <= decision cutoff`. No look-ahead.
- **Three clearly labelled modes** — Decision-time · Retrospective latest · Pick a vintage. Anything that uses a post-cutoff forecast raises an amber _Retrospective_ banner and per-row flags.
- Summary metrics (mean forecast/actual, MAE, RMSE, bias, valid pairs), forecast-vs-actual chart with zoom brush and rich tooltips, per-interval **vintage evolution** chart, error histogram / error-over-time / top-10 errors, sortable + filterable half-hourly error table.
- Data-quality panel: records retrieved, rejected, conflicts resolved, missing actual/forecast, refresh time, cutoff assumption. Missing data is shown as "unavailable", never as zero.
- Explicit **Refresh data** (re-fetch from Elexon), SQLite persistence (no external calls per interaction), OpenAPI docs at `/docs`.

## Architecture & data flow

```
Elexon Insights API ──► ElexonClient (retry/backoff, chunking)
        │                    │
 (or sample fixtures)        ▼
                     normalize.py  (WIND filter, validation, exact-dup removal)
                             │
                             ▼
                      SQLite store  ◄── POST /api/data/refresh (atomic replace; failure keeps old data)
                             │
                      Repository (in-memory snapshot, reloaded after refresh)
                             │
        selection.py ──► analysis.py ──► metrics.py      (pure pandas/numpy, no FastAPI imports)
                             │
                     FastAPI routes (/api/*) ──► React + Recharts dashboard
```

```
backend/app/{api,core,services,models,schemas}/  backend/tests/
frontend/src/{components,hooks,lib,pages,types}/
data/fixtures/   scripts/   docker-compose.yml   render.yaml   .env.example
```

(`features/` from the suggested layout was omitted — this MVP is small enough that `pages/` + `components/` suffice.)

## Elexon data sources

| Purpose  | Dataset | Endpoint                       | Notes                                                              |
| -------- | ------- | ------------------------------ | ------------------------------------------------------------------ |
| Actual   | FUELHH  | `GET /datasets/FUELHH/stream`  | Filter `fuelType == "WIND"`; `generation` = half-hourly average MW |
| Forecast | WINDFOR | `GET /datasets/WINDFOR/stream` | `publishDateTimeFrom/To`                                           |

Base URL `https://data.elexon.co.uk/bmrs/api/v1` (no API key). **Verified from Elexon documentation:** the WINDFOR stream takes `publishDateTimeFrom` / `publishDateTimeTo`; _without them it returns only the latest forecast_, so historical vintages are fetched via publish-time windows (3-day chunks, from 14 days before 1 Jan to 1 Feb). WINDFOR is published up to 8×/day. **Not independently verified:** the FUELHH stream's filter names (the docs pages are JavaScript-rendered and Elexon was unreachable from the build sandbox). The client uses `settlementDateFrom/To` (`yyyy-MM-dd`); a 4xx is surfaced with Elexon's response body so it's quick to correct in `ElexonClient.fetch_actuals`.

## Data assumptions & forecast-selection logic

- Timestamps are parsed to UTC. Delivery dates / settlement dates are **UK local dates** (identical to UTC in January). Intervals must start on :00/:30.
- Generation must be finite and ≥ 0; null/non-numeric/negative values are **rejected and counted**, never zero-filled. A genuine `0` is kept.
- Forecasts are **never deduplicated by `startTime` alone** — each `(startTime, publishTime)` is a vintage. Only _exact_ duplicates are dropped.
- **Duplicate resolution:** rows with the same `(startTime, publishTime)` but different values are _not averaged_; the **lowest** value is kept (deterministic regardless of row order) and the conflict is counted in the data-quality panel. The lowest value is arbitrary but conservative; change `resolve_conflicts` if the desk prefers another rule.
- Actuals: one per interval — the most recent `publishTime` wins (FUELHH can be re-published).
- **Modes:** _cutoff_ = latest `publishTime <= cutoff`; _vintage_ = latest `publishTime <= as_of` (flagged where `> cutoff`); _latest_ = latest `publishTime <= delivery start` (a forecast cannot be published for the past), flagged retrospective.

### Decision cutoff

Default: **09:20 Europe/London on D‑1** (D = delivery date), configurable (`DECISION_CUTOFF_*`, or `cutoff_time` per request). Basis: the GB day-ahead market closes on D‑1 — EPEX SPOT's GB 60‑minute day-ahead auction gate closure is 09:20 UK time and Nord Pool's N2EX closes at 09:50. 09:20 is the earlier of the two so the analysis never credits the buyer with information they could not have used. There is also a GB half-hourly day-ahead auction at 15:30; set the cutoff to `15:30` to analyse that one. Gate times are from exchange documentation and may change — verify before relying on them commercially.

## Metrics

`error = forecast − actual` (MW). **Bias > 0 ⇒ the forecast over-predicted wind; < 0 ⇒ under-predicted.** MAE = mean(|error|), RMSE = √mean(error²), bias = mean(error), all in MW over valid pairs only (both values present; each delivery interval counted once). Energy is shown in GWh as `Σ MW × 0.5 h` — half-hourly MW are never summed as "energy". These are forecast-accuracy measures **only**; they are not costs, losses or savings (no prices or demand are used).

## API

`GET /api/health` · `GET /api/metadata` · `GET /api/wind/actuals` · `GET /api/wind/forecasts` (all vintages) · `GET /api/wind/analysis?start_date&end_date&mode=cutoff|latest|vintage[&as_of][&cutoff_time]` · `GET /api/wind/vintage-times` · `GET /api/wind/vintages?start_time` · `POST /api/data/refresh`. Errors are `{"error":{"code","message","details"}}` (409 no data, 422 invalid input, 502 upstream failure). Swagger UI: `/docs`.

## Configuration

Copy `.env.example` → `.env`. Key variables: `DATA_SOURCE` (`live`|`fixture`), `DECISION_CUTOFF_LOCAL_TIME/TIMEZONE/DAY_OFFSET`, `DATA_START_DATE/END_DATE`, `DATABASE_PATH`, `CORS_ORIGINS`, `VITE_API_BASE_URL` (only if the frontend is hosted separately). No secrets are required.

## Run with Docker Compose

```bash
cp .env.example .env            # set DATA_SOURCE=fixture to run offline with sample data
docker compose up --build       # UI http://localhost:8080  ·  API docs http://localhost:8000/docs
docker compose up --build -d --force-recreate   # rebuild & restart
docker compose down             # stop (data persists in ./data)
```

Both services have health checks; the UI container waits for a healthy API.

## Run locally without Docker

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python ../scripts/generate_sample_fixtures.py     # only if you want sample data
DATA_SOURCE=fixture uvicorn app.main:app --reload --port 8000   # or DATA_SOURCE=live
# frontend (new terminal)
cd frontend && npm install && npm run dev          # http://localhost:5173 (proxies /api → :8000)
```

Real offline data: on a machine that can reach Elexon run `python scripts/capture_fixtures.py`, then use `DATA_SOURCE=fixture`.

## Tests

```bash
cd backend && pytest            # 42 tests: WIND filtering, vintages, cutoff/no-look-ahead, alignment,
                                # duplicates/missing, hand-calculated MAE/RMSE/bias, DST day lengths,
                                # retry/rate-limit/timeout handling, API validation & errors
cd frontend && npm test && npm run typecheck && npm run build
```

## Deployment (not yet deployed)

`render.yaml` is a Render Blueprint (API + nginx-served UI; the API needs a persistent disk, which is a paid Render feature — otherwise it re-fetches on each cold start since `AUTO_REFRESH_ON_EMPTY=true`). Any host that runs Docker (Fly.io, Railway, a VM with `docker compose`) works the same way. Steps: push the repo → create the services → set `DATA_SOURCE=live` and `CORS_ORIGINS` to the UI origin → open `/api/health` → click **Refresh data**. Record the URL here only once it is live.

## Known limitations

- Live Elexon retrieval is unverified end-to-end (see Data sources); the sample fixtures are synthetic and their accuracy numbers mean nothing.
- WINDFOR covers wind farms visible to the system operator with operational metering, so it is not a total-GB figure, and FUELHH WIND may differ in scope; treat bias partly as a scope difference.
- The 09:20 cutoff is an assumption (configurable); real procurement may use other venues/times.
- Single-user, single-month scope; no authentication; chart is not virtualised (fine for ≤ 1,488 points).
- Frontend tests cover formatting/sort/filter/API-error logic, not rendered components.
- GB clock-change days are handled in the backend (46/50 periods) but January data does not exercise it.
