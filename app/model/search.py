from typing import Annotated, Self

from pydantic import BaseModel, AwareDatetime, Field, BeforeValidator, model_validator


def _parse_bbox(value):
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, str):
        return tuple(float(part) for part in value.split(","))
    return value


BBox = Annotated[tuple[float, float, float, float], BeforeValidator(_parse_bbox)]


class SearchRequest(BaseModel):
    bbox: BBox | None = None
    start_datetime: AwareDatetime | None = None
    end_datetime: AwareDatetime | None = None
    max_cloud_coverage: float | None = Field(default=None, ge=0, le=100)
    processing_level: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=10, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _validate_ranges(self) -> Self:
        if self.bbox is not None:
            minx, miny, maxx, maxy = self.bbox
            if not (-180 <= minx <= maxx <= 180):
                raise ValueError("bbox longitudes must be between -180 and 180, with minx <= maxx")
            if not (-90 <= miny <= maxy <= 90):
                raise ValueError("bbox latitudes must be between -90 and 90, with miny <= maxy")
        if self.start_datetime and self.end_datetime and self.start_datetime > self.end_datetime:
            raise ValueError("start_datetime must not be after end_datetime")
        return self
