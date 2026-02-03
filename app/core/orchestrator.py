"""Central Brain orchestrator coordinating pipeline."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.config import Settings
from app.core.image_ops import ImageCropper
from app.core.state_machine import WeightStateMachine
from app.models import FruitDetection, FruitSummary, ScanResult, WeightReading
from app.services import (
    CameraServiceClient,
    DefectDetectorClient,
    FruitDetectorClient,
    MainServerClient,
    UIServiceClient,
    WeightServiceClient,
)

logger = logging.getLogger(__name__)


class BrainOrchestrator:
    """High-level coordinator for weight monitoring and scan execution."""

    def __init__(
        self,
        *,
        settings: Settings,
        weight_client: WeightServiceClient,
        camera_client: CameraServiceClient,
        fruit_detector: FruitDetectorClient,
        defect_detector: DefectDetectorClient,
        ui_client: UIServiceClient,
        main_server_client: MainServerClient,
    ) -> None:
        self.settings = settings
        self.weight_client = weight_client
        self.camera_client = camera_client
        self.fruit_detector = fruit_detector
        self.defect_detector = defect_detector
        self.ui_client = ui_client
        self.main_server_client = main_server_client

        self.state_machine = WeightStateMachine(settings)
        self._poll_task: asyncio.Task[None] | None = None
        self._inflight_scans: set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start background tasks."""

        logger.info("Starting Brain orchestrator")
        self._shutdown_event.clear()
        if self.settings.enable_weight_polling:
            self._poll_task = asyncio.create_task(self._poll_weight_loop(), name="weight-poll")
        else:
            logger.warning("Weight polling disabled via settings; rely on manual scans.")

    async def shutdown(self) -> None:
        """Gracefully stop tasks and close clients."""

        logger.info("Stopping Brain orchestrator")
        self._shutdown_event.set()
        if self._poll_task:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
        await asyncio.gather(*(task for task in self._inflight_scans), return_exceptions=True)
        await asyncio.gather(
            self.weight_client.close(),
            self.camera_client.close(),
            self.fruit_detector.close(),
            self.defect_detector.close(),
            self.ui_client.close(),
            self.main_server_client.close(),
            return_exceptions=True,
        )

    async def _poll_weight_loop(self) -> None:
        poll_interval = self.settings.weight_poll_interval_ms / 1000
        while not self._shutdown_event.is_set():
            try:
                reading = await self.weight_client.read_weight()
                decision = self.state_machine.process(reading)
                if decision.scan_requested:
                    task = asyncio.create_task(
                        self.execute_scan(reading),
                        name=f"scan-{reading.timestamp.isoformat()}",
                    )
                    self._inflight_scans.add(task)
                    task.add_done_callback(self._inflight_scans.discard)
                await asyncio.sleep(poll_interval)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Weight polling failed: %s", exc)
                await asyncio.sleep(poll_interval * 2)

    async def execute_scan(self, reading: WeightReading) -> None:
        session_id = str(uuid4())
        logger.info("Starting scan session=%s weight=%.2f", session_id, reading.grams)

        try:
            # Use primary imgsz for camera resolution (square images for YOLO)
            primary_imgsz = self.settings.fruit_detector_primary_imgsz
            resolution = f"{primary_imgsz}x{primary_imgsz}"
            capture = await self.camera_client.capture_image({"resolution": resolution})
            image_bytes = await self.camera_client.fetch_image_binary(capture.resolved_path())

            # Get image dimensions for bbox area ratio calculations
            cropper = ImageCropper(image_bytes)
            image_width, image_height = cropper.size
            image_area = image_width * image_height

            # Primary detection with configured imgsz
            detections_response = await self.fruit_detector.detect(
                capture.image_id, image_bytes, imgsz=primary_imgsz
            )
            raw_detections = detections_response.fruits

            # Filter by bbox area ratio (remove suspiciously small detections)
            detections_after_bbox_filter = self._filter_detections_by_bbox_area(
                detections=raw_detections,
                image_area=image_area,
                image_id=capture.image_id,
            )

            # Filter by class-specific confidence thresholds
            filtered_detections = self._filter_detections_by_class_threshold(
                detections=detections_after_bbox_filter,
                image_id=capture.image_id,
            )

            # Check if fallback is needed
            fallback_reason = self._should_fallback(
                detections=filtered_detections,
                raw_detections=raw_detections,
                weight_grams=reading.grams,
                image_id=capture.image_id,
            )

            if fallback_reason:
                logger.info(
                    "Triggering fallback detection: image_id=%s reason=%s",
                    capture.image_id,
                    fallback_reason,
                )
                fallback_imgsz = self.settings.fruit_detector_fallback_imgsz
                fallback_response = await self.fruit_detector.detect(
                    capture.image_id, image_bytes, imgsz=fallback_imgsz
                )
                raw_detections_fallback = fallback_response.fruits

                # Apply same filtering to fallback detections
                detections_after_bbox_filter = self._filter_detections_by_bbox_area(
                    detections=raw_detections_fallback,
                    image_area=image_area,
                    image_id=capture.image_id,
                )
                filtered_detections = self._filter_detections_by_class_threshold(
                    detections=detections_after_bbox_filter,
                    image_id=capture.image_id,
                )

                if not filtered_detections:
                    logger.warning(
                        "No fruits detected even after fallback: "
                        "image_id=%s weight=%.2f session=%s",
                        capture.image_id,
                        reading.grams,
                        session_id,
                    )

            fruits = await self._analyze_fruits(
                image_bytes=image_bytes,
                detections=filtered_detections,
                image_id=capture.image_id,
                cropper=cropper,
            )

            result = ScanResult(
                session_id=session_id,
                image_id=capture.image_id,
                timestamp=datetime.now(timezone.utc),
                weight_grams=reading.grams,
                fruits=fruits,
            )

            publish_tasks = [self.ui_client.publish(result)]
            if self.settings.enable_main_server_publish:
                publish_tasks.append(self.main_server_client.publish(result))
            else:
                logger.debug("Main server publish disabled; skipping session=%s", session_id)
            await asyncio.gather(*publish_tasks)
            logger.info("Finished scan session=%s fruits=%d", session_id, len(fruits))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scan %s failed: %s", session_id, exc)

    async def _analyze_fruits(
        self,
        *,
        image_bytes: bytes,
        detections: list[FruitDetection],
        image_id: str,
        cropper: ImageCropper | None = None,
    ) -> list[FruitSummary]:
        if not detections:
            return []

        if cropper is None:
            cropper = ImageCropper(image_bytes)

        async def analyze_detection(detection) -> FruitSummary:
            crop_bytes = await asyncio.to_thread(cropper.crop, detection.bbox)
            try:
                defect_result = await self.defect_detector.detect(
                    image_id=image_id,
                    fruit_id=detection.fruit_id,
                    crop_bytes=crop_bytes,
                    filename=f"{detection.fruit_id}.jpg",
                )
                defects = defect_result.defects
            except Exception as exc:  # noqa: BLE001
                logger.exception("Defect analysis failed for fruit %s: %s", detection.fruit_id, exc)
                defects = []

            return FruitSummary(
                fruit_id=detection.fruit_id,
                fruit_class=detection.fruit_class,
                confidence=detection.confidence,
                bbox=detection.bbox,
                defects=defects,
            )

        tasks = [asyncio.create_task(analyze_detection(det)) for det in detections]
        finished = await asyncio.gather(*tasks, return_exceptions=True)

        fruit_summaries: list[FruitSummary] = []
        for item in finished:
            if isinstance(item, Exception):
                logger.error("Defect analysis task failed: %s", item)
                continue
            fruit_summaries.append(item)
        return fruit_summaries

    def _filter_detections_by_class_threshold(
        self,
        *,
        detections: list[FruitDetection],
        image_id: str,
    ) -> list[FruitDetection]:
        """Filter detections by class-specific confidence thresholds.
        
        Uses settings.fruit_class_thresholds to determine minimum confidence
        per class. Falls back to fruit_detector_confidence_guard for unknown classes.
        """
        if not detections:
            return []

        thresholds = self.settings.fruit_class_thresholds
        fallback_threshold = self.settings.fruit_detector_confidence_guard
        valid_detections: list[FruitDetection] = []

        for detection in detections:
            class_name = detection.fruit_class
            threshold = thresholds.get(class_name, fallback_threshold)

            if detection.confidence >= threshold:
                valid_detections.append(detection)
            elif self.settings.log_discarded_detections_detail:
                logger.info(
                    "Fruit dropped due to low class-specific confidence: "
                    "image_id=%s fruit_id=%s class=%s confidence=%.3f threshold=%.3f",
                    image_id,
                    detection.fruit_id,
                    class_name,
                    detection.confidence,
                    threshold,
                )

        logger.debug(
            "Class threshold filtering: %d/%d detections passed for image_id=%s",
            len(valid_detections),
            len(detections),
            image_id,
        )
        return valid_detections

    def _filter_detections_by_bbox_area(
        self,
        *,
        detections: list[FruitDetection],
        image_area: int,
        image_id: str,
    ) -> list[FruitDetection]:
        """Filter out detections with suspiciously small bounding boxes.
        
        Uses settings.fruit_detector_min_bbox_area_ratio to determine minimum
        acceptable bbox area as a fraction of total image area.
        """
        if not detections:
            return []

        min_area_ratio = self.settings.fruit_detector_min_bbox_area_ratio
        min_area = image_area * min_area_ratio
        valid_detections: list[FruitDetection] = []

        for detection in detections:
            bbox = detection.bbox
            bbox_width = bbox.x_max - bbox.x_min
            bbox_height = bbox.y_max - bbox.y_min
            bbox_area = bbox_width * bbox_height
            area_ratio = bbox_area / image_area if image_area > 0 else 0

            if bbox_area >= min_area:
                valid_detections.append(detection)
            elif self.settings.log_discarded_detections_detail:
                logger.info(
                    "Fruit dropped due to small bbox area: "
                    "image_id=%s fruit_id=%s class=%s "
                    "bbox_area=%.1f area_ratio=%.4f min_ratio=%.4f",
                    image_id,
                    detection.fruit_id,
                    detection.fruit_class,
                    bbox_area,
                    area_ratio,
                    min_area_ratio,
                )

        logger.debug(
            "Bbox area filtering: %d/%d detections passed for image_id=%s",
            len(valid_detections),
            len(detections),
            image_id,
        )
        return valid_detections

    def _should_fallback(
        self,
        *,
        detections: list[FruitDetection],
        raw_detections: list[FruitDetection],
        weight_grams: float,
        image_id: str,
    ) -> str | None:
        """Determine if fallback detection should be triggered.
        
        Returns a reason string if fallback is needed, None otherwise.
        
        Fallback is triggered when:
        1. Weight indicates fruit (>= min_fruit_weight) but no detections
        2. All raw detections have confidence < confidence_guard
        3. Expected more fruits by weight but got fewer
        """
        min_weight = self.settings.min_fruit_weight
        confidence_guard = self.settings.fruit_detector_confidence_guard
        expected_weight_per_fruit = self.settings.fruit_expected_weight_per_fruit

        # Condition 1: Weight indicates fruit but no detections after filtering
        if weight_grams >= min_weight and not detections:
            return "weight_indicates_fruit_but_no_detections"

        # Condition 2: All raw detections have low confidence (below guard)
        if raw_detections and all(d.confidence < confidence_guard for d in raw_detections):
            return "all_detections_below_confidence_guard"

        # Condition 3: Expected more fruits by weight but got fewer
        if weight_grams >= min_weight and expected_weight_per_fruit > 0:
            expected_count = int(weight_grams / expected_weight_per_fruit)
            actual_count = len(detections)
            # Only trigger if we expected at least 2 and got significantly fewer
            if expected_count >= 2 and actual_count < expected_count - 1:
                logger.debug(
                    "Weight-based fruit count mismatch: image_id=%s "
                    "weight=%.1f expected=%d actual=%d",
                    image_id,
                    weight_grams,
                    expected_count,
                    actual_count,
                )
                return "expected_more_fruits_by_weight"

        return None

