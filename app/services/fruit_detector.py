"""Fruit detector HTTP client."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.models import FruitDetections

from .base import BaseServiceClient, ServiceError

logger = logging.getLogger(__name__)


class FruitDetectorClient(BaseServiceClient):
    """Uploads full image for fruit detection."""

    async def detect(
        self,
        image_id: str,
        image_bytes: bytes,
        *,
        filename: str = "full.jpg",
        imgsz: int | None = None,
    ) -> FruitDetections:
        """Send multipart payload and validate JSON response."""

        # API expects the multipart part to be named "file" (FastAPI UploadFile field).
        files = {"file": (filename, image_bytes, "image/jpeg")}
        data = {"image_id": image_id}
        if imgsz is not None:
            data["imgsz"] = imgsz
        raw = await self._post_multipart("/detect-fruits", files=files, data=data)
        try:
            detections = FruitDetections.model_validate(raw)
        except ValidationError as exc:
            raise ServiceError(f"Fruit detector response invalid: {exc}") from exc

        logger.info(
            "Fruit detector found %d fruits for %s imgsz=%s",
            len(detections.fruits),
            image_id,
            imgsz or "default",
        )
        return detections

