"""Application service that drives the keyboard off the UI thread.

Why this exists
---------------
Writing one color to this keyboard's embedded controller takes ~0.5 s. If every
slider movement blocked on that, the UI would be unusable and writes would pile
up, so the keyboard would lag seconds behind the pointer.

:class:`BacklightController` decouples the two: callers publish a *desired state*
(non-blocking) and a single worker thread applies the **latest** one, discarding
intermediate states produced while a write was in flight (latest-wins
coalescing).

The decision of *which* writes a transition needs lives in the pure function
:func:`plan_transition`, so the (subtle) write-minimization logic is unit-tested
with no threads and no I/O. The controller just executes the plan.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum, auto

from .backend import BackendError, KeyboardBackend
from .color import Color
from .state import BacklightState, Mode

__all__ = ["BacklightController", "Operation", "OpKind", "plan_transition"]

logger = logging.getLogger(__name__)


class OpKind(Enum):
    SET_COLOR = auto()
    SET_BRIGHTNESS = auto()
    ENABLE_RAINBOW = auto()
    DISABLE_RAINBOW = auto()
    SET_RAINBOW_SPEED = auto()


@dataclass(frozen=True, slots=True)
class Operation:
    kind: OpKind
    value: Color | int | None = None


def plan_transition(previous: BacklightState, target: BacklightState) -> list[Operation]:
    """Return the minimal, ordered list of hardware operations to go from
    *previous* to *target*. Pure: no side effects, fully unit-testable."""
    if target.mode is Mode.RAINBOW:
        return _plan_rainbow(previous, target)
    return _plan_static(previous, target)


def _plan_rainbow(previous: BacklightState, target: BacklightState) -> list[Operation]:
    entering = previous.mode is not Mode.RAINBOW
    ops: list[Operation] = []
    if entering or previous.rainbow_speed != target.rainbow_speed:
        ops.append(Operation(OpKind.SET_RAINBOW_SPEED, target.rainbow_speed))
    if entering or previous.brightness != target.brightness:
        ops.append(Operation(OpKind.SET_BRIGHTNESS, target.brightness))
    if entering:
        ops.append(Operation(OpKind.ENABLE_RAINBOW))
    return ops


def _plan_static(previous: BacklightState, target: BacklightState) -> list[Operation]:
    leaving_rainbow = previous.mode is Mode.RAINBOW
    ops: list[Operation] = []
    if leaving_rainbow:
        ops.append(Operation(OpKind.DISABLE_RAINBOW))
    # Writing the color re-applies it at the current brightness, so only push it
    # when the keyboard is (or is becoming) lit.
    if target.is_on and (leaving_rainbow or previous.color != target.color):
        ops.append(Operation(OpKind.SET_COLOR, target.color))
    if leaving_rainbow or previous.brightness != target.brightness:
        ops.append(Operation(OpKind.SET_BRIGHTNESS, target.brightness))
    return ops


class BacklightController:
    def __init__(self, backend: KeyboardBackend) -> None:
        self._backend = backend
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self._applied = backend.read_state()
        self._target = self._applied
        self._thread = threading.Thread(target=self._run, name="backlight-writer", daemon=True)

    @property
    def initial_state(self) -> BacklightState:
        return self._applied

    @property
    def max_brightness(self) -> int:
        return self._backend.max_brightness

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop = True
        self._wake.set()
        if self._thread.is_alive():
            self._thread.join(timeout)

    def request(self, state: BacklightState) -> None:
        """Publish the desired state. Returns immediately; the worker applies it."""
        with self._lock:
            self._target = state
        self._wake.set()

    # --------------------------------------------------------------- worker loop
    def _run(self) -> None:
        while not self._stop:
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            while not self._stop:
                with self._lock:
                    target = self._target
                if target == self._applied:
                    break
                self._execute(plan_transition(self._applied, target))
                # Mark applied regardless of write errors: the next request
                # retries, and we must never spin on an unreachable device.
                self._applied = target

    def _execute(self, operations: list[Operation]) -> None:
        for op in operations:
            try:
                self._dispatch(op)
            except BackendError:
                logger.exception("failed applying %s", op.kind.name)

    def _dispatch(self, op: Operation) -> None:
        if op.kind is OpKind.SET_COLOR:
            self._backend.apply_color(op.value)
        elif op.kind is OpKind.SET_BRIGHTNESS:
            self._backend.apply_brightness(op.value)
        elif op.kind is OpKind.ENABLE_RAINBOW:
            self._backend.set_rainbow(True)
        elif op.kind is OpKind.DISABLE_RAINBOW:
            self._backend.set_rainbow(False)
        elif op.kind is OpKind.SET_RAINBOW_SPEED:
            self._backend.set_rainbow_speed(op.value)
