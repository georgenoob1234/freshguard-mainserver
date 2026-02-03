"""FastAPI routes for Brain service."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import BrainOrchestrator
from app.dependencies import get_orchestrator
from app.models import WeightReading

router = APIRouter()


@router.get("/healthz", response_model=dict[str, str])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


class ManualScanRequest(BaseModel):
    weight_grams: float = Field(gt=0)


@router.post("/trigger-scan", response_model=dict[str, str])
async def trigger_scan(
    payload: ManualScanRequest,
    orchestrator: BrainOrchestrator = Depends(get_orchestrator),
) -> dict[str, str]:
    reading = WeightReading(grams=payload.weight_grams, timestamp=datetime.utcnow())
    await orchestrator.execute_scan(reading)
    return {"status": "accepted"}

