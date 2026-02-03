"""Logging helpers for Brain service."""

from __future__ import annotations

import logging
from pathlib import Path

DEFAULT_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "latest.log"


def configure_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """Configure root logger to mirror output to stdout and a fresh log file."""

    log_path = Path(log_file) if log_file else DEFAULT_LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, mode="w", encoding="utf-8"),
        ],
        force=True,
    )

    # Silence noisy httpx request logging (polls weight server every ~100ms)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

