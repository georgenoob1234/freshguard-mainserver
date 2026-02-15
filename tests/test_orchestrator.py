"""Tests for Brain orchestrator pipeline."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from app.config import Settings
from app.core.orchestrator import BrainOrchestrator
from app.models import (
    BoundingBox,
    CameraCaptureResponse,
    DefectDetectionResult,
    DefectInfo,
    FruitDetection,
    FruitDetections,
    ScanResult,
    WeightReading,
)


class DummySettings(Settings):
    model_config = {"env_file": None}


def make_image_bytes(size: int = 128) -> bytes:
    img = Image.new("RGB", (size, size), color=(123, 111, 222))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


class StubWeightClient:
    async def close(self) -> None: ...


class StubCameraClient:
    def __init__(self, image_bytes: bytes) -> None:
        self._image_bytes = image_bytes
        self.capture = CameraCaptureResponse(
            image_id="img-1",
            image_url_or_path="/image/img-1.jpg",
            timestamp=datetime.now(timezone.utc),
        )

    async def capture_image(self) -> CameraCaptureResponse:
        return self.capture

    async def fetch_image_binary(self, _: str) -> bytes:
        return self._image_bytes

    async def close(self) -> None: ...


class StubFruitDetector:
    def __init__(self) -> None:
        self.response = FruitDetections(
            image_id="img-1",
            fruits=[
                FruitDetection(
                    fruit_id="fruit-1",
                    fruit_class="apple",
                    confidence=0.95,
                    bbox=BoundingBox(x_min=0, y_min=0, x_max=60, y_max=60),
                ),
            ],
        )

    async def detect(
        self,
        image_id: str,
        image_bytes: bytes,
        *,
        filename: str = "full.jpg",
        imgsz: int | None = None,
    ) -> FruitDetections:
        return self.response

    async def close(self) -> None: ...


class StubDefectDetector:
    def __init__(self) -> None:
        self.responses = {
            "fruit-1": DefectDetectionResult(
                image_id="img-1",
                fruit_id="fruit-1",
                defects=[DefectInfo(type="bruise", confidence=0.9)],
            )
        }

    async def detect(self, *, image_id: str, fruit_id: str, crop_bytes: bytes, filename: str) -> DefectDetectionResult:
        return self.responses[fruit_id]

    async def close(self) -> None: ...


class RecordingClient:
    def __init__(self) -> None:
        self.results: list[ScanResult] = []

    async def publish(self, result: ScanResult) -> None:
        self.results.append(result)

    async def close(self) -> None: ...


@pytest.mark.asyncio
async def test_execute_scan_sends_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    image_bytes = make_image_bytes()
    settings = DummySettings()

    orchestrator = BrainOrchestrator(
        settings=settings,
        weight_client=StubWeightClient(),  # type: ignore[arg-type]
        camera_client=StubCameraClient(image_bytes),  # type: ignore[arg-type]
        fruit_detector=StubFruitDetector(),  # type: ignore[arg-type]
        defect_detector=StubDefectDetector(),  # type: ignore[arg-type]
        ui_client=RecordingClient(),  # type: ignore[arg-type]
        main_server_client=RecordingClient(),  # type: ignore[arg-type]
    )

    reading = WeightReading(grams=120.0, timestamp=datetime.now(timezone.utc))
    await orchestrator.execute_scan(reading)

    assert orchestrator.ui_client.results  # type: ignore[attr-defined]
    result = orchestrator.ui_client.results[0]  # type: ignore[attr-defined]
    assert result.weight_grams == pytest.approx(120.0)
    assert len(result.fruits) == 1
    assert result.fruits[0].defects[0].type == "bruise"

