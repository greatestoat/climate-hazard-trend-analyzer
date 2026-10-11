from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from app.config import get_settings

MIN_DATE = date(1940, 1, 1)  # start of the ERA5 archive
MIN_SPAN_DAYS = 3 * 365


class CityRegion(BaseModel):
    type: Literal["city"]
    name: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class BBoxRegion(BaseModel):
    type: Literal["bbox"]
    name: str | None = Field(default=None, max_length=120)
    south: float = Field(ge=-90, le=90)
    west: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def check_box(self):
        if self.south >= self.north:
            raise ValueError("south must be less than north")
        if self.west >= self.east:
            raise ValueError("west must be less than east (boxes crossing the antimeridian are not supported)")
        limit = get_settings().max_bbox_span_degrees
        if self.north - self.south > limit or self.east - self.west > limit:
            raise ValueError(f"bounding box may not span more than {limit} degrees in either direction")
        return self


Region = Annotated[Union[CityRegion, BBoxRegion], Field(discriminator="type")]


class AnalysisRequest(BaseModel):
    region: Region
    start_date: date
    end_date: date
    hazard: Literal["heatwave", "cold_wave", "heavy_rainfall"] = "heatwave"
    percentile: float = Field(default=95.0, ge=1.0, le=99.9)
    min_duration: int | None = Field(default=None, ge=1, le=14)
    threshold_method: Literal["period", "seasonal"] = "period"

    @model_validator(mode="after")
    def check_dates(self):
        if self.hazard == "cold_wave" and "percentile" not in self.model_fields_set:
            self.percentile = 5.0
        if self.min_duration is None:
            self.min_duration = 1 if self.hazard == "heavy_rainfall" else 3
        if self.hazard == "cold_wave":
            if not 1 <= self.percentile <= 10:
                raise ValueError("cold-wave percentile must be between 1 and 10")
            if self.min_duration < 3:
                raise ValueError("cold-wave minimum duration must be at least 3 days")
        else:
            if not 90 <= self.percentile <= 99.9:
                raise ValueError("percentile must be between 90 and 99.9")
            if self.hazard == "heatwave" and self.min_duration < 3:
                raise ValueError("heatwave minimum duration must be at least 3 days")
        if self.start_date < MIN_DATE:
            raise ValueError(f"start_date must be {MIN_DATE.isoformat()} or later")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if (self.end_date - self.start_date).days < MIN_SPAN_DAYS:
            raise ValueError("date range must cover at least 3 years to estimate a threshold and trend")
        return self
