"""UI service client for pushing results."""

from __future__ import annotations

import logging

from app.models import ScanResult

from .base import BaseServiceClient

logger = logging.getLogger(__name__)


class UIServiceClient(BaseServiceClient):
    """Pushes aggregated result to UI."""

    async def publish(self, result: ScanResult) -> None:
        payload = result.model_dump(mode="json")
        await self._post_json("/update", payload)
        logger.info("UI update sent session=%s", result.session_id)

