import asyncio
import hashlib
import json
import logging
import uuid
from datetime import date, timedelta

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeout, ValidationFailed
from app.repository import utcnow
from app.schemas import MIN_SPAN_DAYS, AnalysisRequest
from app.services.analysis import analyze, clean_series
from app.services.openmeteo import average_points
from app.services.regions import region_points

log = logging.getLogger(__name__)
INGEST_KEYS = ("rows_received", "invalid_rows", "duplicates_removed", "outliers_removed")


class AnalysisService:
    def __init__(self, repo, weather, settings: Settings):
        self.repo, self.weather, self.s = repo, weather, settings

    async def search_cities(self, q: str):
        return await self.weather.search_cities(q)

    async def create(self, req: AnalysisRequest) -> tuple[dict, bool]:
        warnings: list[str] = []
        start, end = req.start_date, req.end_date
        latest = date.today() - timedelta(days=self.s.archive_lag_days)
        if end > latest:
            end = latest
            warnings.append(f"end_date was moved to {latest.isoformat()}: the archive lags real time by about "
                            f"{self.s.archive_lag_days} days.")
        if (end - start).days < MIN_SPAN_DAYS:
            raise ValidationFailed("date range must cover at least 3 years after adjusting for archive availability")

        points, region_key, representation = region_points(req.region, self.s.bbox_grid_size)
        params = {"region_key": region_key, "start": start.isoformat(), "end": end.isoformat(),
                  "percentile": req.percentile, "min_duration": req.min_duration,
                  "threshold_method": req.threshold_method, "hazard": req.hazard}
        params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()

        await self.repo.ensure_indexes()
        hit = await self.repo.find_analysis_by_hash(params_hash)
        if hit:
            return hit, True

        clean, w = await self._load_weather(region_key, points, start, end)
        warnings += w
        result = await asyncio.to_thread(analyze, clean, start, end, req.percentile,
                                         req.min_duration, req.threshold_method)
        events = result.pop("events")
        now = utcnow()
        doc = {
            "id": uuid.uuid4().hex, "status": "completed", "hazard": req.hazard,
            "created_at": now, "expires_at": now + timedelta(hours=self.s.analysis_cache_ttl_hours),
            "params_hash": params_hash,
            "region": {**req.region.model_dump(), "key": region_key, "representation": representation,
                       "sample_points": len(points)},
            "params": {"start_date": start.isoformat(), "end_date": end.isoformat(),
                       "percentile": req.percentile, "min_duration": req.min_duration,
                       "threshold_method": req.threshold_method},
            "result": result, "warnings": warnings, "events_total": len(events),
        }
        await self.repo.insert_analysis(doc, events)
        return doc, False

    async def _load_weather(self, region_key, points, start: date, end: date):
        s_iso, e_iso = start.isoformat(), end.isoformat()
        fetch = await self.repo.find_fresh_fetch(region_key, s_iso, e_iso)
        if fetch:
            rows = await self.repo.get_weather(region_key, s_iso, e_iso)
            clean = await asyncio.to_thread(clean_series, rows, start, end)
            ingest = fetch.get("quality") or {}
            clean.quality.update({k: ingest[k] for k in INGEST_KEYS if k in ingest})
            clean.quality["source"] = "cache"
            return clean, []
        try:
            series = await self.weather.fetch_daily_tmax(points, start, end)
        except (UpstreamError, UpstreamTimeout) as exc:
            rows = await self.repo.get_weather(region_key, s_iso, e_iso)
            if len(rows) >= 0.9 * ((end - start).days + 1):
                log.warning("Open-Meteo failed (%s); using stored data", exc.message)
                clean = await asyncio.to_thread(clean_series, rows, start, end)
                clean.quality["source"] = "stale_cache"
                return clean, [f"Open-Meteo was unavailable ({exc.message}); previously stored data was used."]
            raise
        rows = await asyncio.to_thread(average_points, series)
        clean = await asyncio.to_thread(clean_series, rows, start, end)
        clean.quality["source"] = "open-meteo"
        stored = [(d.date().isoformat(), float(v)) for d, v in clean.raw_valid.items()]
        await self.repo.save_weather(region_key, s_iso, e_iso, stored, clean.quality)
        return clean, []
