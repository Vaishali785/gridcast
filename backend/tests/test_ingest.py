"""Live/sample labelling and refresh-failure behaviour of the ingest pipeline (mocked Elexon HTTP)."""

import httpx
import pytest
from app.core.config import Settings
from app.core.errors import UpstreamError
from app.services.elexon_client import ElexonClient
from app.services.ingest import refresh_data
from app.services.store import DataStore


def _client(settings, handler):
    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url=settings.elexon_base_url
    )
    return ElexonClient(settings, client=http, sleep=lambda _: None)


def _settings(tmp_path, **kw):
    return Settings(database_path=tmp_path / "t.db", elexon_max_retries=0, **kw)


def handler(req: httpx.Request) -> httpx.Response:
    if "FUELHH" in req.url.path:
        return httpx.Response(
            200,
            json=[
                {
                    "dataset": "FUELHH",
                    "publishTime": "2026-01-01T00:35:00Z",
                    "startTime": "2026-01-01T00:00:00Z",
                    "settlementDate": "2026-01-01",
                    "settlementPeriod": 1,
                    "fuelType": "WIND",
                    "generation": 1000,
                },
                {
                    "dataset": "FUELHH",
                    "publishTime": "2026-01-01T00:35:00Z",
                    "startTime": "2026-01-01T00:00:00Z",
                    "settlementDate": "2026-01-01",
                    "settlementPeriod": 1,
                    "fuelType": "NUCLEAR",
                    "generation": 4000,
                },
            ],
        )
    return httpx.Response(
        200,
        json=[
            {
                "dataset": "WINDFOR",
                "publishTime": "2025-12-31T08:30:00Z",
                "startTime": "2026-01-01T00:00:00Z",
                "generation": 1100,
            }
        ],
    )


def test_successful_live_refresh_is_labelled_live_not_sample(tmp_path):
    s = _settings(tmp_path, data_source="live")
    store = DataStore(s.database_path)
    meta = refresh_data(s, store, client=_client(s, handler))
    assert meta["source"] == "live" and meta["is_sample"] is False
    assert store.refresh_meta()["is_sample"] is False
    assert (
        meta["actuals"]["stored_records"] == 1
        and meta["forecasts"]["stored_records"] == 1
    )


def test_fixture_refresh_is_labelled_sample(tmp_path):
    s = _settings(tmp_path, data_source="fixture")
    store = DataStore(s.database_path)
    assert refresh_data(s, store)["is_sample"] is True


def test_failed_live_refresh_keeps_last_successful_dataset(tmp_path):
    s = _settings(tmp_path, data_source="live")
    store = DataStore(s.database_path)
    first = refresh_data(s, store, client=_client(s, handler))
    with pytest.raises(UpstreamError):
        refresh_data(s, store, client=_client(s, lambda r: httpx.Response(503)))
    kept = store.refresh_meta()
    assert kept["refreshed_at"] == first["refreshed_at"] and kept["source"] == "live"
    assert len(store.load_forecasts()) == 1


def test_empty_live_response_is_an_error_not_an_empty_dataset(tmp_path):
    s = _settings(tmp_path, data_source="live")
    store = DataStore(s.database_path)
    with pytest.raises(UpstreamError):
        refresh_data(
            s, store, client=_client(s, lambda r: httpx.Response(200, json=[]))
        )
    assert store.is_empty()
