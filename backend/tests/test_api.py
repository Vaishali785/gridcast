import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(data_source="fixture", database_path=tmp_path / "t.db", auto_refresh_on_empty=False)
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


Q = {"start_date": "2026-01-10", "end_date": "2026-01-11"}


def test_health_and_empty_state(client):
    assert client.get("/api/health").json() == {"status": "ok", "data_loaded": False}
    assert client.get("/api/metadata").json()["data_loaded"] is False
    r = client.get("/api/wind/analysis", params=Q)
    assert r.status_code == 409 and r.json()["error"]["code"] == "data_not_loaded"


def test_refresh_then_analysis(client):
    r = client.post("/api/data/refresh", json={"source": "fixture"})
    assert r.status_code == 200 and r.json()["is_sample"] is True
    meta = client.get("/api/metadata").json()
    assert meta["data_loaded"] and meta["is_sample_data"] and meta["coverage"]["expected_intervals"] == 31 * 48
    a = client.get("/api/wind/analysis", params=Q).json()
    assert a["mode"] == "cutoff" and a["summary"]["n_lookahead_intervals"] == 0 and not a["is_retrospective"]
    assert len(a["series"]) == 96 and a["metrics"]["n_pairs"] > 0 and a["metrics"]["mae_mw"] > 0
    latest = client.get("/api/wind/analysis", params={**Q, "mode": "latest"}).json()
    assert latest["is_retrospective"] and latest["metrics"]["mae_mw"] < a["metrics"]["mae_mw"]


def test_validation_errors_are_structured(client):
    client.post("/api/data/refresh", json={"source": "fixture"})
    for params in ({"start_date": "2026-01-12", "end_date": "2026-01-10"},
                   {"start_date": "2025-12-01", "end_date": "2025-12-02"},
                   {**Q, "mode": "vintage"}, {**Q, "mode": "nope"}, {**Q, "cutoff_time": "25:99"},
                   {"start_date": "bad", "end_date": "2026-01-10"}):
        r = client.get("/api/wind/analysis", params=params)
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request", params


def test_vintage_evolution_and_forecast_list(client):
    client.post("/api/data/refresh", json={"source": "fixture"})
    v = client.get("/api/wind/vintages", params={"start_time": "2026-01-10T12:00:00Z"}).json()
    assert len(v["vintages"]) >= 3 and v["cutoff_time"].startswith("2026-01-09T09:20")
    assert any(x["available_at_cutoff"] for x in v["vintages"]) and any(not x["available_at_cutoff"] for x in v["vintages"])
    f = client.get("/api/wind/forecasts", params={**Q, "limit": 10}).json()
    assert f["truncated"] and len(f["records"]) == 10


def test_refresh_failure_keeps_existing_data(client, monkeypatch):
    client.post("/api/data/refresh", json={"source": "fixture"})
    before = client.get("/api/metadata").json()["last_successful_refresh"]
    r = client.post("/api/data/refresh", json={"source": "live"})   # sandbox: unreachable / or mocked
    if r.status_code != 200:
        assert r.json()["error"]["code"] == "upstream_error"
        assert client.get("/api/metadata").json()["last_successful_refresh"] == before
