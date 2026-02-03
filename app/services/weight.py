"""Weight service client."""

from __future__ import annotations

import logging
from datetime import datetime

from dateutil import parser as date_parser
from pydantic import ValidationError

from app.models import WeightReading

from .base import BaseServiceClient, ServiceError

logger = logging.getLogger(__name__)


class WeightServiceClient(BaseServiceClient):
    """Simple polling client retrieving weight samples."""

    async def read_weight(self) -> WeightReading:
        """Fetch the latest weight sample."""

        raw = await self._post_json("/read", {})
        try:
            timestamp = raw.get("timestamp")
            if isinstance(timestamp, str):
                raw["timestamp"] = date_parser.isoparse(timestamp)
            elif not isinstance(timestamp, datetime):
                raise ValueError("timestamp missing or invalid")
            reading = WeightReading.model_validate(raw)
        except (ValidationError, ValueError) as exc:
            raise ServiceError(f"Weight reading invalid: {exc}") from exc

        logger.debug("Weight reading %.2f g", reading.grams)
        return reading

