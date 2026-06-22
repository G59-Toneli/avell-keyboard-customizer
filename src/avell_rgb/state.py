"""Backlight state value object.

A single immutable snapshot of what the keyboard should be showing. The
controller diffs successive states to decide the minimal set of hardware writes.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum

from .color import Color

__all__ = ["Mode", "BacklightState"]


class Mode(Enum):
    STATIC = "static"
    RAINBOW = "rainbow"


@dataclass(frozen=True, slots=True)
class BacklightState:
    """Desired keyboard backlight state.

    ``brightness`` is in firmware units (0..max, where 0 means off).
    ``rainbow_speed`` is the firmware effect speed byte (higher = slower) and is
    only meaningful when ``mode is Mode.RAINBOW``.
    """

    mode: Mode
    color: Color
    brightness: int
    rainbow_speed: int

    @property
    def is_on(self) -> bool:
        return self.brightness > 0

    # Immutable "copy-with" helpers keep call sites declarative.
    def with_color(self, color: Color) -> "BacklightState":
        return dataclasses.replace(self, mode=Mode.STATIC, color=color)

    def with_brightness(self, brightness: int) -> "BacklightState":
        return dataclasses.replace(self, brightness=max(0, brightness))

    def with_rainbow(self, enabled: bool) -> "BacklightState":
        return dataclasses.replace(self, mode=Mode.RAINBOW if enabled else Mode.STATIC)

    def with_rainbow_speed(self, speed: int) -> "BacklightState":
        return dataclasses.replace(self, rainbow_speed=max(0, min(255, speed)))
