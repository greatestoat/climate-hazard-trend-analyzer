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
    hazard: Literal["heatwave"] = "heatwave"
    percentile: float = Field(default=95.0, ge=90.0, le=99.9)
    min_duration: int = Field(default=3, ge=3, le=14)
    threshold_method: Literal["period", "seasonal"] = "period"

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date < MIN_DATE:
            raise ValueError(f"start_date must be {MIN_DATE.isoformat()} or later")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if (self.end_date - self.start_date).days < MIN_SPAN_DAYS:
            raise ValueError("date range must cover at least 3 years to estimate a threshold and trend")
        return self
