from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "climate_analyzer"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,https://climate-hazard-trend-analyzer.vercel.ap"

    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_analysis: str = "10/minute"

    weather_cache_ttl_hours: int = 168
    analysis_cache_ttl_hours: int = 168

    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    http_timeout_seconds: float = 60.0
    http_max_retries: int = 3
    http_backoff_seconds: float = 1.0
    archive_lag_days: int = 5  # ERA5 data is published with a few days delay

    bbox_grid_size: int = 3
    max_bbox_span_degrees: float = 10.0

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
