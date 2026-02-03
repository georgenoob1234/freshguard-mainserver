"""Common HTTP client utilities."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ServiceError(RuntimeError):
    """Raised when downstream service interaction fails."""


class BaseServiceClient:
    """Reusable Async HTTP client wrapper."""

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        logger.debug("POST %s payload_keys=%s", url, list(payload.keys()))
        try:
            response = await self._client.post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ServiceError(f"Request to {url} failed: {exc}") from exc

    async def _post_multipart(
        self,
        path: str,
        *,
        files: dict[str, Any],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        logger.debug("POST %s multipart parts=%s", url, list(files.keys()))
        try:
            response = await self._client.post(path, files=files, data=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise ServiceError(f"Multipart request to {url} failed: {exc}") from exc

    async def _get_binary(self, path: str) -> bytes:
        url = f"{self.base_url}{path}"
        logger.debug("GET %s (binary)", url)
        try:
            response = await self._client.get(path)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise ServiceError(f"GET {url} failed: {exc}") from exc

