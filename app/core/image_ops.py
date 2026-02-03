"""Image utilities for cropping fruit bounding boxes."""

from __future__ import annotations

import io
from typing import Iterable

from PIL import Image

from app.models import BoundingBox


class ImageCropper:
    """Wraps a PIL image to generate crops quickly."""

    def __init__(self, image_bytes: bytes) -> None:
        self._buffer = io.BytesIO(image_bytes)
        self._image = Image.open(self._buffer).convert("RGB")

    def crop(self, bbox: BoundingBox) -> bytes:
        """Return JPEG bytes for requested bounding box."""

        crop = self._image.crop(bbox.as_tuple())
        output = io.BytesIO()
        crop.save(output, format="JPEG")
        return output.getvalue()

    @property
    def size(self) -> tuple[int, int]:
        """Return underlying image size as (width, height)."""

        return self._image.size


def crop_all(image_bytes: bytes, boxes: Iterable[BoundingBox]) -> list[bytes]:
    """Convenience helper returning JPEG crops for provided boxes."""

    cropper = ImageCropper(image_bytes)
    return [cropper.crop(bbox) for bbox in boxes]

