"""Camera service client."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.models import CameraCaptureResponse

from .base import BaseServiceClient, ServiceError

logger = logging.getLogger(__name__)


class CameraServiceClient(BaseServiceClient):
    """Handles interactions with the Camera service."""

    async def capture_image(self, payload: dict[str, Any] | None = None) -> CameraCaptureResponse:
        """Trigger capture and validate response."""

        payload = payload or {}
        raw_response = await self._post_json("/capture", payload)
        try:
            capture = CameraCaptureResponse.model_validate(raw_response)
        except ValidationError as exc:
            raise ServiceError(f"Camera response invalid: {exc}") from exc

        logger.info("Captured image %s at %s", capture.image_id, capture.timestamp.isoformat())
        return capture

    async def fetch_image_binary(self, resource_path: str) -> bytes:
        """Download binary image data."""

        binary = await self._get_binary(resource_path)
        logger.info("Fetched image bytes path=%s size=%s", resource_path, len(binary))
        return binary

