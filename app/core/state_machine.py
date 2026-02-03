"""Weight-driven state machine coordinating scan triggers."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta
from statistics import fmean
from typing import Deque

from app.config import Settings
from app.models import ScanDecision, ScanState, WeightReading

logger = logging.getLogger(__name__)


class WeightStateMachine:
    """Encapsulates weight-based event logic with explicit transitions."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state: ScanState = ScanState.IDLE
        self._history: Deque[WeightReading] = deque()
        self._last_scan_at: datetime | None = None
        self._last_scan_weight: float = 0.0

    def process(self, reading: WeightReading) -> ScanDecision:
        """Feed a new reading and return resulting decision."""

        self._history.append(reading)
        self._prune_history(reading.timestamp)

        stable_weight = self._stable_weight()
        if stable_weight is None:
            return ScanDecision(state=self.state, scan_requested=False)

        transition = "NONE"
        scan_requested = False

        if self.state == ScanState.IDLE and stable_weight >= self.settings.min_fruit_weight:
            self.state = ScanState.ACTIVE
            transition = "IDLE->ACTIVE"
            scan_requested = self._mark_scan_if_allowed(stable_weight, reading.timestamp)

        elif self.state == ScanState.ACTIVE:
            if stable_weight < self.settings.min_fruit_weight:
                self.state = ScanState.IDLE
                transition = "ACTIVE->IDLE"
            elif self._significant_delta(stable_weight) and self._scan_interval_respected(reading.timestamp):
                scan_requested = True
                self._last_scan_at = reading.timestamp
                self._last_scan_weight = stable_weight

        if transition != "NONE":
            logger.info("State transition %s weight=%.2f", transition, stable_weight)

        return ScanDecision(
            state=self.state,
            scan_requested=scan_requested,
            transition=transition,
        )

    def _prune_history(self, now: datetime) -> None:
        window = timedelta(milliseconds=self.settings.stable_window_ms)
        while self._history and now - self._history[0].timestamp > window:
            self._history.popleft()

    def _stable_weight(self) -> float | None:
        if len(self._history) < 2:
            return None
        weights = [r.grams for r in self._history]
        if max(weights) - min(weights) > self.settings.weight_noise_epsilon:
            return None
        return float(fmean(weights))

    def _significant_delta(self, weight: float) -> bool:
        return abs(weight - self._last_scan_weight) >= self.settings.significant_delta

    def _scan_interval_respected(self, now: datetime) -> bool:
        if self._last_scan_at is None:
            return True
        elapsed = (now - self._last_scan_at).total_seconds() * 1000
        return elapsed >= self.settings.min_scan_interval_ms

    def _mark_scan_if_allowed(self, weight: float, now: datetime) -> bool:
        if self._scan_interval_respected(now):
            self._last_scan_at = now
            self._last_scan_weight = weight
            return True
        return False

