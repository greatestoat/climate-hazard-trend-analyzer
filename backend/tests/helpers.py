from datetime import date, timedelta

import numpy as np

from app.errors import UpstreamError, UpstreamTimeout
from app.repository import SORT_FIELDS, utcnow


def synthetic_rows(start: date, end: date, warming_per_year=0.0, seed=1, heatwaves=()):
    """Seasonal temperatures + noise. `heatwaves` is a list of (date, length, boost)."""
    rng = np.random.default_rng(seed)
    n = (end - start).days + 1
    rows = []
    for i in range(n):
        d = start + timedelta(days=i)
        t = 28 + 8 * np.sin(2 * np.pi * (d.timetuple().tm_yday - 100) / 365) + rng.normal(0, 1.5)
        t += warming_per_year * (d.year - start.year)
        rows.append([d.isoformat(), float(t)])
    for hd, length, boost in heatwaves:
        for i in range(length):
            idx = (hd - start).days + i
            rows[idx][1] += boost
    return [tuple(r) for r in rows]


class FakeWeather:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows, error, 0

    async def search_cities(self, q):
        return [{"id": 1, "name": q.title(), "country": "India", "admin1": "Telangana",
                 "latitude": 17.38, "longitude": 78.48, "timezone": "Asia/Kolkata", "population": 1}]

    async def fetch_daily_tmax(self, points, start, end):
        self.calls += 1
        if self.error:
            raise self.error
        rows = self.rows or synthetic_rows(start, end, warming_per_year=0.05)
        rows = [r for r in rows if start.isoformat() <= r[0] <= end.isoformat()]
        return [([r[0] for r in rows], [r[1] for r in rows]) for _ in points]


class FakeRepo:
    def __init__(self):
        self.weather, self.fetches, self.analyses, self.events = {}, [], {}, []

    async def close(self): ...
    async def ping(self): return True
    async def ensure_indexes(self): ...

    async def find_fresh_fetch(self, key, start, end):
        for f in self.fetches:
            if f["region_key"] == key and f["start_date"] <= start and f["end_date"] >= end:
                return f
        return None

    async def get_weather(self, key, start, end):
        return sorted((d, v) for (k, d), v in self.weather.items() if k == key and start <= d <= end)

    async def save_weather(self, key, start, end, rows, quality):
        for d, v in rows:
            self.weather[(key, d)] = v
        self.fetches.append({"region_key": key, "start_date": start, "end_date": end, "quality": quality})

    async def find_analysis_by_hash(self, h):
        return next((a for a in self.analyses.values() if a["params_hash"] == h), None)

    async def insert_analysis(self, doc, events):
        self.analyses[doc["id"]] = doc
        self.events += [{**e, "analysis_id": doc["id"]} for e in events]

    async def get_analysis(self, i): return self.analyses.get(i)

    async def query_events(self, aid, year, sort, order, skip, limit):
        ev = [e for e in self.events if e["analysis_id"] == aid and (year is None or e["year"] == year)]
        ev.sort(key=lambda e: e[SORT_FIELDS[sort]], reverse=(order == "desc"))
        return [{k: v for k, v in e.items() if k != "analysis_id"} for e in ev[skip:skip + limit]], len(ev)
