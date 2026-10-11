from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeout
from app.main import create_app
from app.services.openmeteo import OpenMeteoClient, average_points
from app.services.pipeline import AnalysisService
from tests.helpers import FakeRepo, FakeWeather

BODY = {
    "region": {"type": "city", "name": "Hyderabad", "country": "India", "latitude": 17.38, "longitude": 78.48},
    "start_date": "1995-01-01", "end_date": "2019-12-31",
}


def make_client(weather=None, repo=None):
    settings = Settings(rate_limit_enabled=False, http_backoff_seconds=0)
    repo, weather = repo or FakeRepo(), weather or FakeWeather()
    app = create_app(settings, AnalysisService(repo, weather, settings))
    return TestClient(app), repo, weather


def test_health_and_city_search():
    with make_client()[0] as c:
        assert c.get("/api/health").json()["status"] == "ok"
        r = c.get("/api/cities", params={"q": "hyderabad"}).json()
        assert r["results"][0]["name"] == "Hyderabad"
        assert c.get("/api/cities", params={"q": "h"}).status_code == 422


def test_create_get_events_and_cache():
    client, repo, weather = make_client()
    with client as c:
        r = c.post("/api/analyses", json=BODY)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["cached"] is False and data["result"]["summary"]["threshold_c"] > 20
        assert len(data["result"]["annual"]) == 25
        aid = data["id"]

        again = c.post("/api/analyses", json=BODY).json()
        assert again["cached"] is True and again["id"] == aid and weather.calls == 1

        assert c.get(f"/api/analyses/{aid}").json()["id"] == aid
        ev = c.get(f"/api/analyses/{aid}/events", params={"sort": "duration", "order": "desc", "page_size": 5}).json()
        assert ev["total"] == data["events_total"] and len(ev["items"]) <= 5
        if len(ev["items"]) > 1:
            assert ev["items"][0]["duration_days"] >= ev["items"][1]["duration_days"]
        assert all(i["duration_days"] >= 3 for i in ev["items"])


def test_weather_cache_reused_for_different_percentile():
    client, repo, weather = make_client()
    with client as c:
        c.post("/api/analyses", json=BODY)
        c.post("/api/analyses", json={**BODY, "percentile": 97})
        assert weather.calls == 1


def test_bbox_region():
    body = {**BODY, "region": {"type": "bbox", "south": 16, "west": 78, "north": 18, "east": 80}}
    with make_client()[0] as c:
        r = c.post("/api/analyses", json=body)
        assert r.status_code == 201 and r.json()["region"]["sample_points"] == 9


@pytest.mark.parametrize("patch", [
    {"start_date": "2019-01-01", "end_date": "2018-01-01"},
    {"start_date": "2018-01-01", "end_date": "2019-01-01"},          # < 3 years
    {"start_date": "1900-01-01"},
    {"end_date": "2999-01-01"},
    {"min_duration": 2},
    {"hazard": "flood"},
    {"region": {"type": "bbox", "south": 10, "west": 0, "north": 5, "east": 5}},
    {"region": {"type": "bbox", "south": 0, "west": 0, "north": 40, "east": 5}},
    {"region": {"type": "city", "name": "X", "latitude": 99, "longitude": 0}},
])
def test_validation_errors(patch):
    with make_client()[0] as c:
        r = c.post("/api/analyses", json={**BODY, **patch})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_not_found_and_bad_id():
    with make_client()[0] as c:
        assert c.get("/api/analyses/" + "a" * 32).status_code == 404
        assert c.get("/api/analyses/not-valid").status_code == 422
        assert c.get("/api/analyses/" + "a" * 32 + "/events").status_code == 404


@pytest.mark.parametrize("exc,status,code", [
    (UpstreamError("down"), 502, "upstream_error"),
    (UpstreamTimeout("slow"), 504, "upstream_timeout"),
])
def test_upstream_failures_map_to_errors(exc, status, code):
    with make_client(FakeWeather(error=exc))[0] as c:
        r = c.post("/api/analyses", json=BODY)
        assert r.status_code == status and r.json()["error"]["code"] == code


def test_falls_back_to_stored_data_when_api_fails():
    client, repo, weather = make_client()
    with client as c:
        c.post("/api/analyses", json=BODY)
        repo.fetches.clear()                       # simulate expired fetch record, rows remain
        weather.error = UpstreamError("down")
        r = c.post("/api/analyses", json={**BODY, "percentile": 96})
        assert r.status_code == 201 and any("previously stored" in w for w in r.json()["warnings"])


def test_rate_limit_returns_429(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("RATE_LIMIT_ANALYSIS", "2/minute")
    get_settings.cache_clear()
    settings = Settings(rate_limit_enabled=True, rate_limit_analysis="2/minute")
    from app.api import limiter
    limiter.reset()
    app = create_app(settings, AnalysisService(FakeRepo(), FakeWeather(), settings))
    try:
        with TestClient(app) as c:
            codes = [c.post("/api/analyses", json=BODY).status_code for _ in range(3)]
        assert codes[:2] == [201, 201] and codes[2] == 429
    finally:
        limiter.enabled = False
        limiter.reset()
        get_settings.cache_clear()


def test_open_meteo_client_retries_then_succeeds_and_times_out():
    import asyncio
    import httpx

    settings = Settings(http_backoff_seconds=0, http_max_retries=2)
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"daily": {"time": ["2020-01-01"], "temperature_2m_max": [31.2]}})

    async def run():
        c = OpenMeteoClient(settings, httpx.MockTransport(handler))
        s = await c.fetch_daily_tmax([(1.0, 2.0)], date(2020, 1, 1), date(2020, 1, 1))
        await c.aclose()
        return s

    assert asyncio.run(run())[0][1] == [31.2] and calls["n"] == 3

    def slow(req):
        raise httpx.ReadTimeout("t")

    async def run_timeout():
        c = OpenMeteoClient(settings, httpx.MockTransport(slow))
        with pytest.raises(UpstreamTimeout):
            await c.fetch_daily_tmax([(1.0, 2.0)], date(2020, 1, 1), date(2020, 1, 2))

    asyncio.run(run_timeout())


def test_average_points_ignores_missing_values():
    rows = average_points([(["d1", "d2"], [10, None]), (["d1", "d2"], [20, None])])
    assert rows == [("d1", 15.0), ("d2", None)]
