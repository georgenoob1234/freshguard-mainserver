"""Application configuration and constants."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_env: Literal["dev", "prod", "test"] = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Remote services
    weight_service_url: str = Field(default="http://localhost:8100", alias="WEIGHT_SERVICE_URL")
    camera_service_url: str = Field(default="http://localhost:8200", alias="CAMERA_SERVICE_URL")
    fruit_detector_url: str = Field(default="http://localhost:8300", alias="FRUIT_DETECTOR_URL")
    defect_detector_url: str = Field(default="http://localhost:8400", alias="DEFECT_DETECTOR_URL")
    ui_service_url: str = Field(default="http://localhost:8500", alias="UI_SERVICE_URL")
    main_server_url: str = Field(default="http://localhost:8600", alias="MAIN_SERVER_URL")
    enable_main_server_publish: bool = Field(default=False, alias="ENABLE_MAIN_SERVER_PUBLISH")

    # Thresholds and timing (weights in grams, times in milliseconds)
    min_fruit_weight: float = Field(default=30.0, alias="MIN_FRUIT_WEIGHT")
    significant_delta: float = Field(default=20.0, alias="SIGNIFICANT_DELTA")
    weight_noise_epsilon: float = Field(default=5.0, alias="WEIGHT_NOISE_EPSILON")
    stable_window_ms: int = Field(default=400, alias="STABLE_WINDOW_MS")
    min_scan_interval_ms: int = Field(default=2_000, alias="MIN_SCAN_INTERVAL_MS")
    weight_poll_interval_ms: int = Field(default=150, alias="WEIGHT_POLL_INTERVAL_MS")
    enable_weight_polling: bool = Field(default=True, alias="ENABLE_WEIGHT_POLLING")
    fruit_detector_primary_imgsz: int = Field(default=320, alias="FRUIT_DETECTOR_PRIMARY_IMGSZ")
    fruit_detector_fallback_imgsz: int = Field(default=416, alias="FRUIT_DETECTOR_FALLBACK_IMGSZ")
    fruit_detector_confidence_guard: float = Field(
        default=0.30,
        alias="FRUIT_DETECTOR_CONFIDENCE_GUARD",
        ge=0.0,
        le=1.0,
    )
    fruit_detector_min_bbox_area_ratio: float = Field(
        default=0.001,
        alias="FRUIT_DETECTOR_MIN_BBOX_AREA_RATIO",
        ge=0.0,
        le=1.0,
    )
    fruit_expected_weight_per_fruit: float = Field(
        default=100,
        alias="FRUIT_EXPECTED_WEIGHT_PER_FRUIT",
        gt=0.0,
    )
    fruit_class_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "apple": 0.55,
            "banana": 0.40,
            "tomato": 0.60,
        },
        alias="FRUIT_CLASS_THRESHOLDS",
    )
    log_discarded_detections_detail: bool = Field(
        default=False,
        alias="LOG_DISCARDED_DETECTIONS_DETAIL",
        validation_alias=AliasChoices(
            "LOG_DISCARDED_DETECTIONS_DETAIL",
            "log_discarded_detections_detail",
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()  # type: ignore[call-arg]

