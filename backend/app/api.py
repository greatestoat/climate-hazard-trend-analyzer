from typing import Literal
import csv
from io import StringIO

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings
from app.errors import NotFoundError
from app.schemas import AnalysisRequest

limiter = Limiter(key_func=get_remote_address, default_limits=[get_settings().rate_limit_default])
router = APIRouter(prefix="/api")
AnalysisId = Path(pattern=r"^[a-f0-9]{32}$", description="Analysis id")


def _svc(request: Request):
    return request.app.state.service


def _serialize(doc: dict, cached: bool | None = None) -> dict:
    out = {k: v for k, v in doc.items() if k != "params_hash"}
    if cached is not None:
        out["cached"] = cached
    return out


@router.get("/health")
async def health(request: Request):
    db_ok = await request.app.state.service.repo.ping()
    return {"status": "ok" if db_ok else "degraded", "database": "up" if db_ok else "down", "version": "1.0.0"}


@router.get("/cities")
async def search_cities(request: Request, q: str = Query(min_length=2, max_length=80)):
    return {"query": q, "results": await _svc(request).search_cities(q.strip())}


@router.post("/analyses", status_code=201)
@limiter.limit(lambda: get_settings().rate_limit_analysis)
async def create_analysis(request: Request, body: AnalysisRequest):
    doc, cached = await _svc(request).create(body)
    return _serialize(doc, cached)


@router.get("/analyses/{analysis_id}")
async def get_analysis(request: Request, analysis_id: str = AnalysisId):
    doc = await _svc(request).repo.get_analysis(analysis_id)
    if not doc:
        raise NotFoundError("Analysis not found or expired.")
    return _serialize(doc)


@router.get("/analyses/{analysis_id}/events")
async def get_events(
    request: Request,
    analysis_id: str = AnalysisId,
    year: int | None = Query(default=None, ge=1940, le=2100),
    sort: Literal["start", "duration", "peak", "intensity"] = "start",
    order: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=20, ge=1, le=100),
):
    repo = _svc(request).repo
    if not await repo.get_analysis(analysis_id):
        raise NotFoundError("Analysis not found or expired.")
    items, total = await repo.query_events(analysis_id, year, sort, order, (page - 1) * page_size, page_size)
    return {"analysis_id": analysis_id, "total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/analyses/{analysis_id}/events.csv")
async def export_events_csv(
    request: Request,
    analysis_id: str = AnalysisId,
    year: int | None = Query(default=None, ge=1940, le=2100),
):
    repo = _svc(request).repo
    if not await repo.get_analysis(analysis_id):
        raise NotFoundError("Analysis not found or expired.")

    async def rows():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["start", "end", "year", "duration_days", "peak_temp_c", "peak_date",
                         "mean_temp_c", "mean_excess_c", "cumulative_excess_c", "threshold_c"])
        yield output.getvalue()
        offset = 0
        while True:
            events, total = await repo.query_events(analysis_id, year, "start", "asc", offset, 500)
            if not events:
                break
            output.seek(0)
            output.truncate(0)
            for event in events:
                writer.writerow([event.get(k, "") for k in (
                    "start", "end", "year", "duration_days", "peak_temp_c", "peak_date",
                    "mean_temp_c", "mean_excess_c", "cumulative_excess_c", "threshold_c")])
            yield output.getvalue()
            offset += len(events)
            if offset >= total:
                break

    suffix = f"-{year}" if year else ""
    return StreamingResponse(rows(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="heatwave-events-{analysis_id}{suffix}.csv"',
    })
