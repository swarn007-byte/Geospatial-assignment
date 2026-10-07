"""Pydantic response schemas."""
from typing import Any, Optional
from pydantic import BaseModel


class FileInfoResponse(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: Optional[str] = None
    status: str

    class Config:
        from_attributes = True


class FeatureMeasurement(BaseModel):
    feature_id: int
    geometry_type: str
    crs: Optional[str] = None
    properties: dict[str, Any] = {}
    measurement: Optional[dict[str, Any]] = None
    # Raw GeoJSON geometry, useful for clients that want to render
    geometry: Optional[dict[str, Any]] = None


class MeasurementsResponse(BaseModel):
    id: str
    filename: str
    crs: Optional[str] = None
    measurement_crs: Optional[str] = None
    feature_count: int
    measurements: list[FeatureMeasurement]
