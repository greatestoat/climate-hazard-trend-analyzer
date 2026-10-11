import asyncio
import logging
from datetime import date

import httpx

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeout

log = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


class OpenMeteoClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.s = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds),
            transport=transport,
            headers={"User-Agent": "climate-hazard-analyzer/1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get_json(self, url: str, params: dict):
        last: Exception | None = None
        for attempt in range(self.s.http_max_retries + 1):
            try:
                r = await self._client.get(url, params=params)
                if r.status_code in RETRY_STATUS:
                    msg = "Open-Meteo rate limit reached; try again shortly." if r.status_code == 429 \
                        else f"Open-Meteo returned HTTP {r.status_code}."
                    last = UpstreamError(msg)
                elif r.status_code >= 400:
                    try:
                        reason = r.json().get("reason", r.text[:200])
                    except Exception:
                        reason = r.text[:200]
                    raise UpstreamError(f"Open-Meteo rejected the request: {reason}")
                else:
                    try:
                        return r.json()
                    except ValueError:
                        last = UpstreamError("Open-Meteo returned an unreadable response.")
            except httpx.TimeoutException:
                last = UpstreamTimeout("Open-Meteo timed out.")
            except httpx.TransportError:
                last = UpstreamError("Could not reach Open-Meteo.")
            if attempt < self.s.http_max_retries:
                delay = self.s.http_backoff_seconds * (2 ** attempt)
                log.warning("Open-Meteo attempt %d failed (%s); retrying in %.1fs", attempt + 1, last, delay)
                await asyncio.sleep(delay)
        assert last is not None
        raise last

    async def search_cities(self, query: str, count: int = 8) -> list[dict]:
        data = await self._get_json(
            self.s.open_meteo_geocoding_url,
            {"name": query, "count": count, "language": "en", "format": "json"},
        )
        out = []
        for r in data.get("results") or []:
            out.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "country": r.get("country"),
                "admin1": r.get("admin1"),
                "latitude": r.get("latitude"),
                "longitude": r.get("longitude"),
                "timezone": r.get("timezone"),
                "population": r.get("population"),
            })
        return out

    async def fetch_daily_tmax(self, points: list[tuple[float, float]], start: date, end: date):
        """Returns one (dates, values) pair per requested point."""
        params = {
            "latitude": ",".join(f"{p[0]:.4f}" for p in points),
            "longitude": ",".join(f"{p[1]:.4f}" for p in points),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "models": "era5",
            "daily": "temperature_2m_max",
            "timezone": "auto",
        }
        data = await self._get_json(self.s.open_meteo_archive_url, params)
        blocks = data if isinstance(data, list) else [data]
        series = []
        for b in blocks:
            daily = (b or {}).get("daily") or {}
            times, vals = daily.get("time"), daily.get("temperature_2m_max")
            if times is None or vals is None or len(times) != len(vals):
                raise UpstreamError("Open-Meteo returned an unexpected data format.")
            series.append((times, vals))
        if len(series) != len(points):
            raise UpstreamError("Open-Meteo returned fewer locations than requested.")
        return series


def average_points(series: list[tuple[list, list]]) -> list[tuple[str, float | None]]:
    """Average per-point series into one regional series (positional; ignores missing points)."""
    times = series[0][0]
    rows = []
    for i, d in enumerate(times):
        vals = []
        for t, v in series:
            if i < len(v) and v[i] is not None:
                vals.append(float(v[i]))
        rows.append((d, sum(vals) / len(vals) if vals else None))
    return rows
