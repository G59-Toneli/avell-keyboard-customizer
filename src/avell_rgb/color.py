"""Color domain.

A small, immutable :class:`Color` value object plus pure HSV<->RGB conversions.

This module is deliberately free of any I/O, threading or GUI imports so it can
be reasoned about and unit-tested in complete isolation (it is the innermost
layer of the architecture).
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

__all__ = ["Color"]


def _clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))


@dataclass(frozen=True, slots=True)
class Color:
    """An immutable 8-bit-per-channel RGB color.

    Instances are validated on construction and hashable, which makes them safe
    to compare and to use as cache/diff keys in the controller.
    """

    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        for name, value in (("red", self.red), ("green", self.green), ("blue", self.blue)):
            if not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(f"{name} must be an int in 0..255, got {value!r}")

    # ----------------------------------------------------------------- factories
    @classmethod
    def from_hsv(cls, hue: float, saturation: float, value: float) -> "Color":
        """Build a color from HSV. ``hue`` is in degrees [0, 360); ``saturation``
        and ``value`` are in [0, 1]."""
        r, g, b = colorsys.hsv_to_rgb((hue % 360.0) / 360.0, _unit(saturation), _unit(value))
        return cls(round(r * 255), round(g * 255), round(b * 255))

    @classmethod
    def from_hex(cls, text: str) -> "Color":
        """Parse ``#RRGGBB`` (or ``RRGGBB``)."""
        cleaned = text.strip().lstrip("#")
        if len(cleaned) != 6:
            raise ValueError(f"expected a 6-digit hex color, got {text!r}")
        return cls(int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16))

    @classmethod
    def from_triplet(cls, values: tuple[int, int, int]) -> "Color":
        r, g, b = values
        return cls(_clamp_channel(r), _clamp_channel(g), _clamp_channel(b))

    # ----------------------------------------------------------------- accessors
    def to_hsv(self) -> tuple[float, float, float]:
        """Return ``(hue_degrees, saturation, value)``."""
        h, s, v = colorsys.rgb_to_hsv(self.red / 255, self.green / 255, self.blue / 255)
        return h * 360.0, s, v

    @property
    def hex(self) -> str:
        return f"#{self.red:02X}{self.green:02X}{self.blue:02X}"

    @property
    def is_black(self) -> bool:
        return self.red == 0 and self.green == 0 and self.blue == 0

    @property
    def as_triplet(self) -> tuple[int, int, int]:
        return self.red, self.green, self.blue


def _unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


# Named colors used by the CLI and the GUI presets.
NAMED_COLORS: dict[str, Color] = {
    "red": Color(255, 0, 0),
    "orange": Color(255, 45, 0),
    "amber": Color(255, 150, 0),
    "yellow": Color(255, 255, 0),
    "green": Color(0, 255, 0),
    "teal": Color(0, 200, 120),
    "cyan": Color(0, 255, 255),
    "blue": Color(0, 120, 255),
    "indigo": Color(0, 0, 255),
    "violet": Color(140, 0, 255),
    "magenta": Color(255, 0, 255),
    "pink": Color(255, 60, 140),
    "white": Color(255, 255, 255),
}
