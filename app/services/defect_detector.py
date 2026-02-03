"""Defect detector client."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.models import DefectDetectionResult

from .base import BaseServiceClient, ServiceError

logger = logging.getLogger(__name__)


LOW_CONFIDENCE_THRESHOLD = 0.3


class DefectDetectorClient(BaseServiceClient):
    """Uploads fruit crop for defect detection."""

    async def detect(
        self,
        *,
        image_id: str,
        fruit_id: str,
        crop_bytes: bytes,
        filename: str,
    ) -> DefectDetectionResult:
        logger.debug(
            "Sending crop to defect detector: fruit_id=%s, size=%d bytes",
            fruit_id,
            len(crop_bytes),
        )

        files = {"image": (filename, crop_bytes, "image/jpeg")}
        data = {"image_id": image_id, "fruit_id": fruit_id}
        raw = await self._post_multipart("/detect-defects", files=files, data=data)
        try:
            result = DefectDetectionResult.model_validate(raw)
        except ValidationError as exc:
            raise ServiceError(f"Defect detector response invalid: {exc}") from exc

        # INFO-level summary
        logger.info(
            "Defect detector found %d defects for fruit %s (image %s)",
            len(result.defects),
            fruit_id,
            image_id,
        )

        # DEBUG-level defect details
        if result.defects:
            defect_summary = ", ".join(
                f"{d.type} ({d.confidence:.2f})" for d in result.defects
            )
            logger.debug("Defect details for %s: %s", fruit_id, defect_summary)

            # WARNING-level for low confidence defects
            low_conf_defects = [
                d for d in result.defects if d.confidence < LOW_CONFIDENCE_THRESHOLD
            ]
            if low_conf_defects:
                low_conf_summary = ", ".join(
                    f"{d.type} ({d.confidence:.2f})" for d in low_conf_defects
                )
                logger.warning(
                    "Low confidence defects detected for %s: %s",
                    fruit_id,
                    low_conf_summary,
                )

        return result

