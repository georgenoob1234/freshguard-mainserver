"""FastAPI entrypoint for Brain service."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router as api_router
from app.config import Settings, get_settings
from app.core import BrainOrchestrator
from app.logging import configure_logging
from app.services import (
    CameraServiceClient,
    DefectDetectorClient,
    FruitDetectorClient,
    MainServerClient,
    UIServiceClient,
    WeightServiceClient,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    orchestrator = BrainOrchestrator(
        settings=settings,
        weight_client=WeightServiceClient(str(settings.weight_service_url)),
        camera_client=CameraServiceClient(str(settings.camera_service_url)),
        fruit_detector=FruitDetectorClient(str(settings.fruit_detector_url)),
        defect_detector=DefectDetectorClient(str(settings.defect_detector_url)),
        ui_client=UIServiceClient(str(settings.ui_service_url)),
        main_server_client=MainServerClient(str(settings.main_server_url)),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.orchestrator = orchestrator
        await orchestrator.start()
        try:
            yield
        finally:
            await orchestrator.shutdown()

    app = FastAPI(title="Brain Service", version="0.1.0", lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()

