"""Unit tests for weight state machine."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.state_machine import WeightStateMachine
from app.models import ScanState, WeightReading


class StubSettings:
    min_fruit_weight = 30.0
    significant_delta = 20.0
    weight_noise_epsilon = 5.0
    stable_window_ms = 500
    min_scan_interval_ms = 2_000


def reading(weight: float, offset_ms: int) -> WeightReading:
    ts = datetime.fromtimestamp(offset_ms / 1000)
    return WeightReading(grams=weight, timestamp=ts)


def test_initial_transition_triggers_scan() -> None:
    machine = WeightStateMachine(StubSettings())  # type: ignore[arg-type]

    # Feed stable readings above min_fruit_weight within the stable window
    machine.process(reading(35, 0))
    decision = machine.process(reading(35, 100))

    assert decision.state == ScanState.ACTIVE
    assert decision.scan_requested is True


def test_significant_delta_requests_new_scan_after_interval() -> None:
    machine = WeightStateMachine(StubSettings())  # type: ignore[arg-type]

    machine.process(reading(32, 0))
    machine.process(reading(33, 100))

    machine.process(reading(60, 3_100))
    decision = machine.process(reading(62, 3_300))

    assert decision.scan_requested is True


def test_return_to_idle_when_weight_removed() -> None:
    machine = WeightStateMachine(StubSettings())  # type: ignore[arg-type]

    # First enter ACTIVE state with stable readings
    machine.process(reading(32, 0))
    machine.process(reading(33, 100))

    # Provide stable low readings to trigger ACTIVE->IDLE
    machine.process(reading(0, 3_500))
    decision = machine.process(reading(0, 3_600))
    assert decision.state == ScanState.IDLE

