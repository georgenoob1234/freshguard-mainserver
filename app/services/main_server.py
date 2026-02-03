"""Client for main server / telegram integration."""

from __future__ import annotations

import logging

from app.models import ScanResult

from .base import BaseServiceClient

logger = logging.getLogger(__name__)


class MainServerClient(BaseServiceClient):
    """Push final scan result upstream."""

    async def publish(self, result: ScanResult) -> None:
        payload = result.model_dump(mode="json")
        await self._post_json("/ingest", payload)
        logger.info("Main server update sent session=%s", result.session_id)

