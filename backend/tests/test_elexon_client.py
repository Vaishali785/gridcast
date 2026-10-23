import httpx
import pytest

from app.core.config import Settings
from app.core.errors import UpstreamError
from app.services.elexon_client import ElexonClient


def make(handler, retries=2):
    s = Settings(elexon_max_retries=retries)
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=s.elexon_base_url)
    return ElexonClient(s, client=http, sleep=lambda _: None)


def test_returns_array_and_unwraps_data_envelope():
    c = make(lambda r: httpx.Response(200, json={"data": [{"a": 1}]}))
    assert c._get_json("/x", {}) == [{"a": 1}]


def test_retries_rate_limit_then_succeeds():
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "1"}) if calls["n"] < 3 else httpx.Response(200, json=[])
    assert make(h)._get_json("/x", {}) == [] and calls["n"] == 3


def test_gives_up_with_structured_error_after_retries():
    with pytest.raises(UpstreamError):
        make(lambda r: httpx.Response(503))._get_json("/x", {})


def test_client_error_not_retried_and_includes_body():
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(400, text="bad param")
    with pytest.raises(UpstreamError) as e:
        make(h)._get_json("/x", {"p": "1"})
    assert calls["n"] == 1 and e.value.details["body"] == "bad param"


def test_timeout_is_reported():
    def h(req):
        raise httpx.ReadTimeout("slow")
    with pytest.raises(UpstreamError, match="failed after"):
        make(h)._get_json("/x", {})


def test_non_json_and_wrong_shape():
    with pytest.raises(UpstreamError):
        make(lambda r: httpx.Response(200, text="<html>"))._get_json("/x", {})
    with pytest.raises(UpstreamError):
        make(lambda r: httpx.Response(200, json={"oops": 1}))._get_json("/x", {})


def test_forecast_fetch_uses_publish_window_chunks():
    seen = []

    def h(req):
        seen.append(dict(req.url.params))
        return httpx.Response(200, json=[])
    from datetime import datetime, timezone
    c = make(h)
    c.fetch_forecasts(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 7, tzinfo=timezone.utc), chunk_days=3)
    assert len(seen) == 2 and seen[0]["publishDateTimeFrom"] == "2026-01-01T00:00:00Z"
    assert seen[1]["publishDateTimeTo"] == "2026-01-07T00:00:00Z"
