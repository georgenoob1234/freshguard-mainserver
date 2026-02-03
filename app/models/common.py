"""Common Pydantic models shared across modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Sequence

from pydantic import BaseModel, Field, NonNegativeFloat, PositiveFloat, model_validator


class BoundingBox(BaseModel):
    """Axis-aligned bounding box, defined in pixel coordinates."""

    model_config = {"populate_by_name": True}

    x_min: NonNegativeFloat
    y_min: NonNegativeFloat
    x_max: PositiveFloat
    y_max: PositiveFloat

    @model_validator(mode="before")
    @classmethod
    def _coerce_sequence(cls, value):
        """Allow list/tuple inputs from detectors while preserving dict API."""

        if isinstance(value, (str, bytes)):
            return value
        if isinstance(value, dict):
            return value
        if isinstance(value, Sequence):
            if len(value) != 4:
                raise ValueError("BoundingBox sequence must contain four values")
            x_min, y_min, x_max, y_max = value
            return {
                "x_min": x_min,
                "y_min": y_min,
                "x_max": x_max,
                "y_max": y_max,
            }
        return value

    def as_tuple(self) -> tuple[int, int, int, int]:
        """Return bounding box as Pillow-friendly tuple."""

        return (
            int(self.x_min),
            int(self.y_min),
            int(self.x_max),
            int(self.y_max),
        )


class DefectMask(BaseModel):
    """Optional segmentation mask details."""

    polygon: Sequence[tuple[float, float]] = Field(default_factory=list)


class DefectInfo(BaseModel):
    """Single detected defect description."""

    type: str
    confidence: float = Field(ge=0.0, le=1.0)
    segmentation: DefectMask | None = None


class FruitDetection(BaseModel):
    """Single fruit detection from FruitDetector."""

    fruit_id: str
    fruit_class: str = Field(alias="class")
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox

    model_config = {"populate_by_name": True}


class FruitDetections(BaseModel):
    """Wrapper for detector response."""

    image_id: str
    fruits: list[FruitDetection]


class DefectDetectionResult(BaseModel):
    """DefectDetector response structure."""

    image_id: str
    fruit_id: str
    defects: list[DefectInfo]


class WeightReading(BaseModel):
    """Single weight sample from weight service."""

    grams: float = Field(ge=0.0)
    timestamp: datetime


class ScanState(str, Enum):
    """Possible machine states."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"


class ScanDecision(BaseModel):
    """Outcome of feeding a reading into the state machine."""

    state: ScanState
    scan_requested: bool = False
    transition: Literal["IDLE->ACTIVE", "ACTIVE->IDLE", "NONE"] = "NONE"


class FruitSummary(BaseModel):
    """Single fruit entry in final payload."""

    fruit_id: str
    fruit_class: str
    confidence: float
    bbox: BoundingBox
    defects: list[DefectInfo]


class ScanResult(BaseModel):
    """Payload forwarded to UI and main server."""

    session_id: str
    image_id: str
    timestamp: datetime
    weight_grams: float
    fruits: list[FruitSummary]


class CameraCaptureResponse(BaseModel):
    """Camera service capture metadata."""

    image_id: str
    image_url: str | None = Field(default=None, alias="image_url_or_path")
    image_path: str | None = None
    timestamp: datetime

    model_config = {"populate_by_name": True}

    def resolved_path(self) -> str:
        """Return preferred path or URL for downloading binary data."""

        if self.image_path:
            return self.image_path
        if self.image_url:
            return self.image_url
        raise ValueError("Camera did not provide image location")

