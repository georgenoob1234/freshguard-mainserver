"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Request

from app.core import BrainOrchestrator


def get_orchestrator(request: Request) -> BrainOrchestrator:
    orchestrator: BrainOrchestrator | None = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return orchestrator

