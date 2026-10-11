import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import limiter, router
from app.config import Settings, get_settings
from app.errors import AppError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("climate")


def _err(
    status: int,
    code: str,
    message: str,
    details=None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )


def create_app(
    settings: Settings | None = None,
    service=None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = service is None

        if owned:
            from app.repository import MongoRepository
            from app.services.openmeteo import OpenMeteoClient
            from app.services.pipeline import AnalysisService

            repo = MongoRepository(settings)
            weather = OpenMeteoClient(settings)

            app.state.service = AnalysisService(
                repo,
                weather,
                settings,
            )

            try:
                await repo.ensure_indexes()
            except Exception as exc:
                # The database may become available later.
                # Index creation can be retried by the application.
                log.warning(
                    "MongoDB not reachable at startup: %s",
                    exc,
                )
        else:
            app.state.service = service

        try:
            yield
        finally:
            if owned:
                await app.state.service.weather.aclose()
                await app.state.service.repo.close()

    app = FastAPI(
        title="Climate Hazard Trend Analyzer",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Rate limiting configuration
    limiter.enabled = settings.rate_limit_enabled
    app.state.limiter = limiter

    # CORS configuration
    # This middleware must wrap the application so browser
    # OPTIONS preflight requests can be handled correctly.
    app.add_middleware(
        SlowAPIMiddleware,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )

    # Application-specific errors
    @app.exception_handler(AppError)
    async def app_error(
        request: Request,
        exc: AppError,
    ):
        return _err(
            exc.status_code,
            exc.code,
            exc.message,
            exc.details,
        )

    # Request validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request,
        exc: RequestValidationError,
    ):
        details = [
            {
                "field": ".".join(
                    str(part) for part in error["loc"][1:]
                ),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]

        return _err(
            422,
            "validation_error",
            "The request is invalid.",
            jsonable_encoder(details),
        )

    # Rate limit errors
    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(
        request: Request,
        exc: RateLimitExceeded,
    ):
        return _err(
            429,
            "rate_limited",
            "Too many requests. Wait a moment and try again.",
        )

    # MongoDB errors
    @app.exception_handler(PyMongoError)
    async def mongo_error(
        request: Request,
        exc: PyMongoError,
    ):
        log.error("MongoDB error: %s", exc)

        return _err(
            503,
            "database_unavailable",
            "The database is unavailable. Check that MongoDB is running.",
        )

    # Unexpected server errors
    @app.exception_handler(Exception)
    async def unhandled(
        request: Request,
        exc: Exception,
    ):
        log.exception("Unhandled error")

        return _err(
            500,
            "internal_error",
            "Something went wrong on the server.",
        )

    # Register API routes
    app.include_router(router)

    return app


app = create_app()