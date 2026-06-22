"""Hardware backend: the port (interface) and its sysfs adapter.

The rest of the application depends only on the abstract :class:`KeyboardBackend`
(Dependency Inversion). The concrete :class:`SysfsKeyboardBackend` is the *only*
place that knows about device paths and the Uniwill EC quirks; swapping it for a
fake (see ``tests/``) or a future per-key backend requires no changes elsewhere.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .color import Color
from .state import BacklightState, Mode

__all__ = ["KeyboardBackend", "SysfsKeyboardBackend", "SysfsPaths", "BackendError"]


class BackendError(RuntimeError):
    """Raised when the keyboard hardware cannot be reached or written."""


class KeyboardBackend(ABC):
    """Granular operations on a single-zone RGB keyboard backlight.

    Methods are intentionally fine-grained (one concern each) so the controller
    can issue the *minimum* number of writes — each one is slow on this hardware.
    Implementations may block; the controller calls them off the UI thread.
    """

    @property
    @abstractmethod
    def max_brightness(self) -> int: ...

    @property
    @abstractmethod
    def supports_rainbow(self) -> bool:
        """Whether the firmware rainbow effect is available (patched driver)."""

    @abstractmethod
    def read_state(self) -> BacklightState:
        """Read the current hardware state (used to initialise the UI)."""

    @abstractmethod
    def apply_color(self, color: Color) -> None: ...

    @abstractmethod
    def apply_brightness(self, level: int) -> None: ...

    @abstractmethod
    def set_rainbow(self, enabled: bool) -> None: ...

    @abstractmethod
    def set_rainbow_speed(self, speed: int) -> None: ...


@dataclass(frozen=True, slots=True)
class SysfsPaths:
    """Filesystem locations exposed by the (patched) tuxedo-drivers module."""

    led: Path = Path("/sys/class/leds/rgb:kbd_backlight")
    platform: Path = Path("/sys/devices/platform/tuxedo_keyboard")

    @property
    def multi_intensity(self) -> Path:
        return self.led / "multi_intensity"

    @property
    def brightness(self) -> Path:
        return self.led / "brightness"

    @property
    def max_brightness(self) -> Path:
        return self.led / "max_brightness"

    @property
    def rainbow(self) -> Path:
        return self.platform / "kbd_rainbow"

    @property
    def rainbow_speed(self) -> Path:
        return self.platform / "kbd_rainbow_speed"


class SysfsKeyboardBackend(KeyboardBackend):
    """Drives the keyboard through the Linux LED + platform sysfs interface."""

    _DEFAULT_MAX_BRIGHTNESS = 4
    _DEFAULT_SPEED = 0x80

    def __init__(self, paths: SysfsPaths | None = None) -> None:
        self._paths = paths or SysfsPaths()
        self._max_brightness = self._read_int(self._paths.max_brightness, self._DEFAULT_MAX_BRIGHTNESS)
        self._supports_rainbow = os.access(self._paths.rainbow, os.W_OK)

    # ------------------------------------------------------------- capabilities
    @property
    def max_brightness(self) -> int:
        return self._max_brightness

    @property
    def supports_rainbow(self) -> bool:
        return self._supports_rainbow

    def is_available(self) -> bool:
        """True when the keyboard LED interface is present and writable."""
        return os.access(self._paths.multi_intensity, os.W_OK)

    # ------------------------------------------------------------------- reading
    def read_state(self) -> BacklightState:
        color = self._read_color()
        brightness = self._read_int(self._paths.brightness, self._max_brightness)
        if self._supports_rainbow:
            rainbow_on = self._read_int(self._paths.rainbow, 0) == 1
            speed = self._read_int(self._paths.rainbow_speed, self._DEFAULT_SPEED)
        else:
            rainbow_on = False
            speed = self._DEFAULT_SPEED
        return BacklightState(
            mode=Mode.RAINBOW if rainbow_on else Mode.STATIC,
            color=color,
            brightness=brightness,
            rainbow_speed=speed,
        )

    # ------------------------------------------------------------------- writing
    def apply_color(self, color: Color) -> None:
        self._write(self._paths.multi_intensity, f"{color.red} {color.green} {color.blue}")

    def apply_brightness(self, level: int) -> None:
        clamped = max(0, min(self._max_brightness, level))
        self._write(self._paths.brightness, str(clamped))

    def set_rainbow(self, enabled: bool) -> None:
        if self._supports_rainbow:
            self._write(self._paths.rainbow, "1" if enabled else "0")

    def set_rainbow_speed(self, speed: int) -> None:
        if self._supports_rainbow:
            self._write(self._paths.rainbow_speed, str(max(0, min(255, speed))))

    # -------------------------------------------------------------------- helpers
    def _read_color(self) -> Color:
        try:
            parts = self._paths.multi_intensity.read_text().split()
            return Color.from_triplet((int(parts[0]), int(parts[1]), int(parts[2])))
        except (OSError, ValueError, IndexError):
            return Color(61, 69, 240)  # brand blue fallback

    @staticmethod
    def _read_int(path: Path, default: int) -> int:
        try:
            return int(path.read_text().split()[0])
        except (OSError, ValueError, IndexError):
            return default

    @staticmethod
    def _write(path: Path, value: str) -> None:
        # The EC can be transiently busy; one retry smooths that over. A second
        # failure is surfaced so the caller (controller) can log it.
        last: OSError | None = None
        for _ in range(2):
            try:
                path.write_text(value)
                return
            except OSError as exc:  # noqa: PERF203 - tiny, two-iteration loop
                last = exc
        raise BackendError(f"failed writing {value!r} to {path}: {last}")
