"""Integration test for the controller using a fake backend (Dependency Inversion
makes this possible without any hardware)."""

import threading
import time

from avell_rgb.backend import KeyboardBackend
from avell_rgb.color import Color
from avell_rgb.controller import BacklightController
from avell_rgb.state import BacklightState, Mode


class FakeBackend(KeyboardBackend):
    def __init__(self, initial: BacklightState) -> None:
        self._initial = initial
        self.calls: list[tuple[str, object]] = []
        self._lock = threading.Lock()

    @property
    def max_brightness(self) -> int:
        return 4

    @property
    def supports_rainbow(self) -> bool:
        return True

    def read_state(self) -> BacklightState:
        return self._initial

    def _record(self, name: str, value: object) -> None:
        with self._lock:
            self.calls.append((name, value))

    def apply_color(self, color: Color) -> None:
        self._record("color", color)

    def apply_brightness(self, level: int) -> None:
        self._record("brightness", level)

    def set_rainbow(self, enabled: bool) -> None:
        self._record("rainbow", enabled)

    def set_rainbow_speed(self, speed: int) -> None:
        self._record("speed", speed)

    def snapshot(self) -> list[tuple[str, object]]:
        with self._lock:
            return list(self.calls)


def _wait_for(predicate, timeout=2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("timed out waiting for the worker")


def _start(initial: BacklightState) -> tuple[BacklightController, FakeBackend]:
    backend = FakeBackend(initial)
    controller = BacklightController(backend)
    controller.start()
    return controller, backend


def test_applies_requested_color():
    controller, backend = _start(BacklightState(Mode.STATIC, Color(0, 0, 0), 0, 0x80))
    try:
        controller.request(BacklightState(Mode.STATIC, Color(255, 0, 0), 4, 0x80))
        _wait_for(lambda: ("color", Color(255, 0, 0)) in backend.snapshot())
        assert ("brightness", 4) in backend.snapshot()
    finally:
        controller.stop()


def test_enabling_rainbow_emits_speed_and_enable():
    controller, backend = _start(BacklightState(Mode.STATIC, Color(255, 0, 0), 4, 0x80))
    try:
        controller.request(BacklightState(Mode.RAINBOW, Color(255, 0, 0), 4, 0x20))
        _wait_for(lambda: ("rainbow", True) in backend.snapshot())
        calls = backend.snapshot()
        assert ("speed", 0x20) in calls
        assert calls.index(("speed", 0x20)) < calls.index(("rainbow", True))
    finally:
        controller.stop()


def test_stop_joins_cleanly():
    controller, _ = _start(BacklightState(Mode.STATIC, Color(0, 0, 0), 0, 0x80))
    controller.stop()  # must not hang
