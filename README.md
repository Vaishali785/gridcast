# GridCast — UK Wind Forecast Intelligence

GridCast is a wind-generation forecast analytics dashboard for a UK electricity procurement team. It shows the wind forecast that was **actually available when the day-ahead purchase decision was made**, and measures how accurate that forecast was against actual wind generation. It uses Elexon BMRS data for **January 2026** delivery dates.

- **Frontend:** React, Vite, TypeScript, Tailwind CSS, Recharts
- **Backend:** Python, FastAPI, pandas, SQLite
- **Tests:** pytest (backend), Vitest (frontend)
- **Packaging:** Docker, Docker Compose

---

## Contents

1. [Purpose and users](#purpose-and-users)
2. [Features](#features)
3. [Architecture and data flow](#architecture-and-data-flow)
4. [Project structure](#project-structure)
5. [Elexon data sources](#elexon-data-sources)
6. [Data assumptions and forecast-selection logic](#data-assumptions-and-forecast-selection-logic)
7. [Metrics](#metrics)
8. [API reference](#api-reference)
9. [Configuration](#configuration)
10. [Run locally (without Docker)](#run-locally-without-docker)
11. [Run with Docker Compose](#run-with-docker-compose)
12. [Tests](#tests)
13. [Verifying your data](#verifying-your-data)
14. [Deployment](#deployment)
15. [Known limitations](#known-limitations)
16. [Troubleshooting](#troubleshooting)
17. [AI tools used](#ai-tools-used)

---

## Purpose and users

GridCast is for analysts on a procurement desk that buys from the GB day-ahead wholesale market. It answers four questions:

1. What wind did the forecast predict **at the time we bought**?
2. What wind was actually generated?
3. How wrong was the forecast, in which direction, and when?
4. How did the forecast for a given half-hour change as new forecasts were published?

It deliberately does **not** estimate money. Wholesale prices and customer demand are not part of the data, so the metrics are in MW and are not costs, losses or savings.

## Features

- **Decision-time forecast selection.** For every half-hour, the latest forecast published at or before the decision cutoff is used. Nothing published later is used, so there is no look-ahead.
- **Three clearly labelled modes:**
  - **Decision-time:** what was known when the purchase was made.
  - **Retrospective latest:** the latest forecast published before delivery. This was not known at decision time.
  - **Pick a vintage:** the latest forecast published at or before a time you choose.
- **Retrospective warning.** Any view that uses a post-cutoff forecast shows an amber notice, and affected rows are flagged.
- **Overview:** date range and mode selectors, a status row (sample/live and missing-data count), MAE, RMSE and Bias cards, and the Forecast vs Actual chart with a zoom brush and detailed tooltips.
- **Collapsible detail sections:**
  - **Forecast vintages:** how the forecast for one half-hour changed across publications, against the decision cutoff and the actual value.
  - **Error analysis:** error histogram, error over time, the ten largest errors, and a sortable, filterable half-hourly table.
  - **Data quality and assumptions:** records retrieved, rejected, conflicts resolved, missing intervals, refresh time and the cutoff assumption.
- **Honest missing data.** A missing value is shown as unavailable and is never treated as zero. A genuine 0 MW reading is kept.
- **Persistence and refresh.** Retrieved data is stored in SQLite, so chart interactions never call Elexon. An explicit **Refresh data** button re-fetches. A failed refresh keeps the last good dataset.
- **Interactive API docs** at `/docs` (Swagger UI).

## Architecture and data flow

```
Elexon Insights API ──► ElexonClient (retry/backoff, chunked requests)
        │                      │
 (or sample fixtures)          ▼
                       normalize.py   WIND filter, validation, exact-duplicate removal
                               │
                               ▼
                        SQLite store  ◄── POST /api/data/refresh
                               │          (atomic replace; a failed refresh keeps old data)
                        Repository    in-memory snapshot, reloaded after each refresh
                               │
         selection.py ──► analysis.py ──► metrics.py     pure pandas/numpy, no FastAPI imports
                               │
                       FastAPI routes (/api/*)  ──►  React + Recharts dashboard
```

Calculation logic (`selection.py`, `analysis.py`, `metrics.py`) is independent of FastAPI and the frontend. The frontend never computes metrics; it displays what the API returns.

## Project structure

```
gridcast/
├── backend/
│   ├── app/
│   │   ├── api/routes.py            HTTP routes (validation and serialisation only)
│   │   ├── core/                    config.py (settings), errors.py (structured errors)
│   │   ├── models/domain.py         SelectionMode, CutoffRule
│   │   ├── schemas/api.py           Pydantic request/response models (OpenAPI)
│   │   ├── services/
│   │   │   ├── elexon_client.py     HTTP client: retries, rate limits, chunking, fixtures
│   │   │   ├── normalize.py         validation, WIND filter, duplicate resolution
│   │   │   ├── selection.py         forecast-vintage selection (no look-ahead)
│   │   │   ├── analysis.py          alignment, summary, top errors, histogram
│   │   │   ├── metrics.py           MAE, RMSE, bias, MWh
│   │   │   ├── ingest.py            fetch → validate → persist pipeline
│   │   │   ├── store.py             SQLite persistence
│   │   │   └── repository.py        cached snapshot of stored data
│   │   └── main.py                  FastAPI app, CORS, error handlers
│   ├── tests/                       pytest suite
│   ├── requirements.txt / requirements-dev.txt / pytest.ini
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/              Header, Controls, SummaryCards, ForecastChart,
│   │   │                            VintagePanel, ErrorAnalysis, ErrorTable, DataQuality, States
│   │   ├── hooks/useAsync.ts        cancellable data fetching
│   │   ├── lib/                     api.ts, format.ts, table.ts, chart.ts, lib.test.ts
│   │   ├── pages/Dashboard.tsx      overview + collapsible detail sections
│   │   ├── types/api.ts             types mirroring the backend schemas
│   │   ├── App.tsx, main.tsx, index.css
│   ├── nginx.conf.template, Dockerfile
│   └── package.json, vite.config.ts, tailwind.config.js, tsconfig.json
├── data/
│   └── fixtures/                    SAMPLE fixtures (synthetic) in the Elexon schema
├── scripts/
│   ├── generate_sample_fixtures.py  regenerate the synthetic sample data
│   ├── capture_fixtures.py          capture REAL Elexon responses for offline use
│   └── inspect_live_data.py         read-only diagnostics for stored data
├── docker-compose.yml, render.yaml
├── .env.example, .gitignore
└── README.md
```

## Elexon data sources

| Purpose             | Dataset | Endpoint                       | Key facts                                                            |
| ------------------- | ------- | ------------------------------ | -------------------------------------------------------------------- |
| Actual generation   | FUELHH  | `GET /datasets/FUELHH/stream`  | Half-hourly. Filter `fuelType == "WIND"`. `generation` is MW.        |
| Forecast generation | WINDFOR | `GET /datasets/WINDFOR/stream` | **Hourly** (`startTime` on the hour). Published several times a day. |

Base URL: `https://data.elexon.co.uk/bmrs/api/v1`. No API key is required.

- **WINDFOR parameters** (`publishDateTimeFrom`, `publishDateTimeTo`) are taken from Elexon's documentation. Without them the endpoint returns only the **latest** forecast, so historical vintages are fetched by publish-time window: 3-day chunks, from 14 days before 1 January up to 1 February.
- **FUELHH parameters** (`settlementDateFrom`, `settlementDateTo`, in `yyyy-MM-dd`) could not be confirmed from the documentation, because the docs pages are JavaScript-rendered. If Elexon rejects them, the API returns a structured error that includes Elexon's response body, so the fix is quick (`ElexonClient.fetch_actuals`).
- **Pagination:** the stream endpoints return the full result for the requested window. Nothing in the code paginates. If you ever see truncated data, run the diagnostics (see below).

### Live and sample data

GridCast runs in one of two data modes, shown in the interface (the header badge and the status row on the Overview):

| Mode            | `DATA_SOURCE` | Meaning                                                                                                  |
| --------------- | ------------- | -------------------------------------------------------------------------------------------------------- |
| **Live data**   | `live`        | Data retrieved from the Elexon Insights API and stored locally after a successful refresh                |
| **Sample data** | `fixture`     | Synthetic records in the Elexon schema from `data/fixtures/`, for development and offline demonstrations |

The label reflects how the stored data was obtained. A failed refresh leaves the last successful dataset and its label unchanged.

## Data assumptions and forecast-selection logic

### Timestamps and validation

- All timestamps are parsed to timezone-aware UTC. Delivery dates are UK local dates (identical to UTC in January).
- Delivery intervals must start on :00 or :30. Misaligned records are rejected and counted.
- Generation must be finite and ≥ 0. Null, non-numeric, infinite and negative values are **rejected and counted**, never zero-filled. A genuine `0` is kept.
- `settlementDate`, `settlementPeriod` and `publishTime` are preserved.

### Vintages and duplicates

- Forecasts are **never deduplicated by `startTime` alone.** Each `(startTime, publishTime)` pair is a separate vintage. Only exact duplicates (same start, publish time and value) are dropped.
- **Conflicting duplicates** (same `startTime` and `publishTime`, different values) are not averaged. The **lowest** value is kept, which is deterministic regardless of row order, and the conflict is counted in the data-quality panel. The choice is arbitrary but conservative; change `resolve_conflicts` if your desk prefers another rule.
- Actuals: one value per interval. The most recently published record wins (FUELHH can be re-published).

### Decision cutoff

The default is **09:20 Europe/London on D-1**, where D is the delivery date. It is configurable through `DECISION_CUTOFF_*` settings, or per request with the `cutoff_time` parameter.

The basis is that the GB day-ahead market closes on D-1. EPEX SPOT's GB 60-minute day-ahead auction closes at 09:20 UK time, and Nord Pool's N2EX at 09:50. The earlier time is used so that the analysis never credits the buyer with information they could not have used. There is also a half-hourly day-ahead auction at 15:30; set the cutoff to `15:30` to analyse that one. Gate times come from exchange documentation and can change, so verify them before relying on them commercially.

### Selection modes

| Mode      | Forecast used for each delivery interval                                          |
| --------- | --------------------------------------------------------------------------------- |
| `cutoff`  | Latest forecast with `publishTime <=` the interval's decision cutoff              |
| `vintage` | Latest forecast with `publishTime <= as_of` (flagged where later than the cutoff) |
| `latest`  | Latest forecast with `publishTime <=` the delivery start (retrospective, flagged) |

### Hourly forecasts and half-hourly actuals

WINDFOR is hourly and FUELHH is half-hourly, so only about half of the half-hours have a forecast with a matching `startTime`.

- An interval uses a forecast with exactly its own `startTime` if one exists.
- Otherwise, a :30 interval uses the forecast for the hour that contains it. One hourly value is applied to both half-hours of its hour.
- The cutoff and vintage rules are unchanged. An hour with no forecast stays missing and is never filled.
- The data-quality panel reports how many half-hours rely on this.
- Set `EXPAND_HOURLY_FORECASTS=false` to pair only exact `startTime` matches (roughly half the intervals).

This is a resolution choice, not extra information. The alternative, averaging the two half-hour actuals into an hourly value, would halve the number of pairs.

## Metrics

```
error = forecast − actual        (MW)
```

| Metric | Definition                                                                                             |
| ------ | ------------------------------------------------------------------------------------------------------ |
| MAE    | mean of \|error\|                                                                                      |
| RMSE   | square root of the mean of error²                                                                      |
| Bias   | mean of error. **Positive means the forecast over-predicted wind; negative means it under-predicted.** |

- All values are in MW, calculated over **valid pairs only**: intervals with both a valid forecast and a valid actual. Each delivery interval is counted once.
- Missing values are never treated as zero.
- Energy is shown as `Σ MW × 0.5 h`. Half-hourly MW readings are never summed and labelled as energy.
- These are accuracy measures only. They are not procurement costs or savings.

## API reference

Interactive docs: `http://localhost:8000/docs`.

| Method and route                                                    | Purpose                                                                              |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `GET /api/health`                                                   | Liveness and whether data is loaded                                                  |
| `GET /api/metadata`                                                 | Source, sample/live flag, last refresh, cutoff, coverage, ingest stats               |
| `GET /api/wind/actuals?start_date&end_date`                         | Resolved WIND actuals (MW)                                                           |
| `GET /api/wind/forecasts?start_date&end_date&limit`                 | **All** forecast vintages in range                                                   |
| `GET /api/wind/analysis?start_date&end_date&mode&as_of&cutoff_time` | Summary, metrics, per-interval series, top errors, histogram                         |
| `GET /api/wind/vintage-times?start_date&end_date`                   | Distinct forecast publication times, for the vintage selector                        |
| `GET /api/wind/vintages?start_time`                                 | How the forecast for one half-hour evolved                                           |
| `POST /api/data/refresh`                                            | Re-fetch from Elexon (or fixtures); body `{"source": "live"\|"fixture"}` is optional |

`mode` is `cutoff` (default), `latest` or `vintage`. `vintage` requires a timezone-aware `as_of`, for example `2026-01-10T08:30:00Z`.

Errors are structured:

```json
{ "error": { "code": "invalid_request", "message": "…", "details": {} } }
```

| Status | `code`            | Meaning                                           |
| ------ | ----------------- | ------------------------------------------------- |
| 409    | `data_not_loaded` | No data yet. Call refresh.                        |
| 422    | `invalid_request` | Invalid dates, mode, cutoff or timestamp          |
| 502    | `upstream_error`  | Elexon request failed (the previous data is kept) |

## Configuration

Copy `.env.example` to `.env`. No secrets are required.

| Variable                                        | Default                                       | Purpose                                                                              |
| ----------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `DATA_SOURCE`                                   | `live`                                        | `live` fetches from Elexon. `fixture` loads `data/fixtures/*.json` (sample data).    |
| `ELEXON_BASE_URL`                               | `https://data.elexon.co.uk/bmrs/api/v1`       | Elexon Insights API                                                                  |
| `ELEXON_TIMEOUT_SECONDS` / `ELEXON_MAX_RETRIES` | `60` / `4`                                    | HTTP timeout and retry count                                                         |
| `AUTO_REFRESH_ON_EMPTY`                         | `true`                                        | Load data at startup if the database is empty                                        |
| `DATA_START_DATE` / `DATA_END_DATE`             | `2026-01-01` / `2026-01-31`                   | Delivery-date window (UK dates)                                                      |
| `FORECAST_PUBLISH_LOOKBACK_DAYS`                | `14`                                          | How far before the window to fetch forecast publications                             |
| `DECISION_CUTOFF_LOCAL_TIME`                    | `09:20`                                       | Cutoff time (local market time)                                                      |
| `DECISION_CUTOFF_TIMEZONE`                      | `Europe/London`                               | Cutoff timezone                                                                      |
| `DECISION_CUTOFF_DAY_OFFSET`                    | `-1`                                          | Cutoff day relative to delivery date (D-1)                                           |
| `EXPAND_HOURLY_FORECASTS`                       | `true`                                        | Apply each hourly forecast to both half-hours of its hour                            |
| `DATABASE_PATH`                                 | `data/gridcast.db`                            | SQLite file                                                                          |
| `CORS_ORIGINS`                                  | `http://localhost:5173,http://localhost:8080` | Allowed browser origins                                                              |
| `VITE_API_BASE_URL`                             | _(empty)_                                     | Frontend build-time API URL; only needed if the UI is hosted separately from the API |

## Run locally (without Docker)

**Prerequisites:** Python 3.11+ and Node.js 18+.

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env             # then edit DATA_SOURCE as needed

# Sample data (offline):
python ../scripts/generate_sample_fixtures.py
DATA_SOURCE=fixture uvicorn app.main:app --reload --port 8000

# Live Elexon data:
DATA_SOURCE=live uvicorn app.main:app --reload --port 8000
```

On Windows PowerShell, set the variable with `$env:DATA_SOURCE="fixture"` before running `uvicorn`.

**Frontend** (new terminal)

```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173, proxies /api to :8000
```

**Offline real data:** on a machine that can reach Elexon, run `python scripts/capture_fixtures.py`. It writes real responses into `data/fixtures/`, after which `DATA_SOURCE=fixture` serves real, offline January 2026 data.

## Run with Docker Compose

```bash
cp .env.example .env                   # set DATA_SOURCE=fixture to run offline
docker compose up --build              # UI: http://localhost:8080   API docs: http://localhost:8000/docs
```

| Task                                         | Command                                         |
| -------------------------------------------- | ----------------------------------------------- |
| Rebuild and restart everything               | `docker compose up --build -d --force-recreate` |
| Rebuild only the frontend (after UI changes) | `docker compose up --build -d frontend`         |
| Stop (data persists in `./data`)             | `docker compose down`                           |

Both services have health checks, and the UI container waits for a healthy API. A plain restart does **not** pick up code changes, because the images contain the built code, so use `--build`.

## Tests

```bash
cd backend && pytest                   # 52 tests
cd frontend && npm test                # 13 tests
cd frontend && npm run typecheck && npm run build
```

Backend tests cover WIND filtering; vintage preservation; cutoff selection and look-ahead prevention; hourly-forecast alignment; duplicates, conflicts and missing data; hand-calculated MAE, RMSE and bias; DST day lengths; Elexon client retries, rate limits and timeouts; live/sample labelling and failed-refresh behaviour; and API validation and structured errors.

Frontend tests cover number formatting, table sorting and filtering, API error parsing, and the chart-series logic that keeps forecast values visible. They do not render components.

## Verifying your data

After a live refresh, run:

```bash
python scripts/inspect_live_data.py          # inspects the stored data, no network needed
python scripts/inspect_live_data.py --raw    # also fetches one raw day from Elexon
```

It prints plain counts:

- whether forecasts are hourly or half-hourly;
- how many forecasts were published **after** their delivery time;
- how often the same value repeats across publications;
- how complete the actuals are;
- the ratio of mean forecast to mean actual.

A forecast/actual ratio far from 1.0 usually means the two datasets differ in **scope** (for example metered versus embedded wind), not that the data is wrong.

## Deployment

**Deployed URL:** [Live URL](https://gridcast-vaishali.vercel.app/)

`render.yaml` is a Render Blueprint with two services: the API, and the nginx-served UI that proxies `/api` to it. Any host that runs Docker (Fly.io, Railway, or a VM with `docker compose`) works the same way.

1. Push the repository to GitHub.
2. Create the services from `render.yaml` (or your host's equivalent).
3. Set `DATA_SOURCE=live`, and set `CORS_ORIGINS` to the UI's origin.
4. Open `/api/health`, then click **Refresh data** in the UI.

The API needs a persistent disk for `/data`, which is a paid Render feature. Without one it re-fetches on each cold start, because `AUTO_REFRESH_ON_EMPTY=true`. Add the deployed URL above once the service is live.

## Known limitations

- Sample fixtures are synthetic and intended for development and demonstration only.
- The FUELHH filter parameter names should be confirmed against Elexon's current API documentation (see [Elexon data sources](#elexon-data-sources)).
- Hourly WINDFOR values are applied to both half-hours of their hour. This is a resolution choice and adds no information.
- WINDFOR and FUELHH may differ in scope, so a persistent bias is not necessarily forecast error.
- Some WINDFOR records may carry a publish time after the delivery start. The Decision-time and Retrospective modes never use them; the vintage panel shows them as post-cutoff points. Use `scripts/inspect_live_data.py` to see how many exist in your data.
- The 09:20 cutoff is an assumption. Real procurement may use other venues or times.
- Single user, single month, no authentication.
- The Docker configuration targets local development. Validate it in your environment with `docker compose up --build`.
- GB clock-change days (46 or 50 half-hours) are handled in the backend, but January data does not exercise this.
- Chart rendering is not virtualised, which is fine for up to 1,488 points.

## Troubleshooting

| Symptom                                   | Likely cause and fix                                                                                                      |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| UI says the backend is unreachable        | Backend is not running, or the proxy target is wrong. Start it on port 8000, or set `VITE_API_PROXY`.                     |
| "No data loaded yet"                      | Click **Load data** / **Refresh data**, or set `AUTO_REFRESH_ON_EMPTY=true`.                                              |
| Refresh fails with `upstream_error`       | Read the message. A 4xx from Elexon includes its response body; a timeout or 5xx is retried first. Previous data is kept. |
| About half the half-hours show as missing | Forecasts are hourly. Ensure `EXPAND_HOURLY_FORECASTS=true` and restart the backend.                                      |
| UI changes don't appear (Docker)          | Rebuild: `docker compose up --build -d frontend`, then hard-refresh the browser.                                          |
| Backend test import errors                | Run `pytest` from inside `backend/` (it sets `pythonpath`).                                                               |

## AI tools used

Claude (Anthropic) and ChatGPT (OpenAI) were used as AI coding assistants during development to help draft code, tests, documentation, and troubleshoot issues. Design decisions, implementation choices, assumptions, and results were reviewed by the author.
