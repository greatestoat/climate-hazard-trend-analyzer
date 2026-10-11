from datetime import datetime, timedelta, timezone

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, UpdateOne

from app.config import Settings

SORT_FIELDS = {"start": "start", "duration": "duration_days", "peak": "peak_temp_c", "intensity": "cumulative_excess_c"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MongoRepository:
    def __init__(self, settings: Settings):
        self.s = settings
        self.client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=4000)
        self.db = self.client[settings.mongodb_db]
        self._indexed = False

    async def close(self):
        await self.client.close()

    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    async def ensure_indexes(self):
        if self._indexed:
            return
        d = self.db
        await d.weather_daily.create_index([("region_key", ASCENDING), ("date", ASCENDING)], unique=True)
        await d.weather_fetches.create_index([("region_key", ASCENDING), ("start_date", ASCENDING), ("end_date", ASCENDING)])
        await d.weather_fetches.create_index("expires_at", expireAfterSeconds=0)
        await d.analyses.create_index("params_hash")
        await d.analyses.create_index("expires_at", expireAfterSeconds=0)
        await d.heatwave_events.create_index([("analysis_id", ASCENDING), ("start", ASCENDING)])
        await d.heatwave_events.create_index([("analysis_id", ASCENDING), ("year", ASCENDING)])
        await d.heatwave_events.create_index("expires_at", expireAfterSeconds=0)
        self._indexed = True

    # ---- weather -------------------------------------------------------
    async def find_fresh_fetch(self, region_key: str, start: str, end: str):
        return await self.db.weather_fetches.find_one(
            {"region_key": region_key, "start_date": {"$lte": start}, "end_date": {"$gte": end},
             "expires_at": {"$gt": utcnow()}}, {"_id": 0})

    async def get_weather(self, region_key: str, start: str, end: str) -> list[tuple[str, float]]:
        cur = self.db.weather_daily.find(
            {"region_key": region_key, "date": {"$gte": start, "$lte": end}},
            {"_id": 0, "date": 1, "tmax": 1}).sort("date", ASCENDING)
        return [(r["date"], r["tmax"]) async for r in cur]

    async def save_weather(self, region_key: str, start: str, end: str, rows: list[tuple[str, float]], quality: dict):
        now = utcnow()
        for i in range(0, len(rows), 5000):
            ops = [UpdateOne({"region_key": region_key, "date": d},
                             {"$set": {"tmax": float(v), "fetched_at": now}}, upsert=True)
                   for d, v in rows[i:i + 5000]]
            if ops:
                await self.db.weather_daily.bulk_write(ops, ordered=False)
        await self.db.weather_fetches.insert_one({
            "region_key": region_key, "start_date": start, "end_date": end, "fetched_at": now,
            "expires_at": now + timedelta(hours=self.s.weather_cache_ttl_hours), "quality": quality})

    # ---- analyses ------------------------------------------------------
    async def find_analysis_by_hash(self, params_hash: str):
        doc = await self.db.analyses.find_one({"params_hash": params_hash, "expires_at": {"$gt": utcnow()}})
        return _public(doc)

    async def insert_analysis(self, doc: dict, events: list[dict]):
        await self.db.analyses.insert_one({**doc, "_id": doc["id"]})
        if events:
            await self.db.heatwave_events.insert_many(
                [{**e, "analysis_id": doc["id"], "expires_at": doc["expires_at"]} for e in events])

    async def get_analysis(self, analysis_id: str):
        return _public(await self.db.analyses.find_one({"_id": analysis_id}))

    async def query_events(self, analysis_id: str, year: int | None, sort: str, order: str, skip: int, limit: int):
        flt = {"analysis_id": analysis_id}
        if year is not None:
            flt["year"] = year
        total = await self.db.heatwave_events.count_documents(flt)
        direction = ASCENDING if order == "asc" else DESCENDING
        cur = (self.db.heatwave_events.find(flt, {"_id": 0, "analysis_id": 0, "expires_at": 0})
               .sort([(SORT_FIELDS[sort], direction), ("start", ASCENDING)]).skip(skip).limit(limit))
        return [e async for e in cur], total


def _public(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc
