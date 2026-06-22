"""``kbcolor`` — a small command-line front-end.

One-shot and synchronous (no worker thread needed): it drives the same backend
the GUI uses. Examples::

    kbcolor blue                 # a named color, full brightness
    kbcolor "#ff8800"            # hex
    kbcolor 255 128 0            # explicit RGB
    kbcolor blue --brightness 2
    kbcolor off
    kbcolor rainbow --speed slow
    kbcolor rainbow --off
    kbcolor status
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .backend import BackendError, SysfsKeyboardBackend
from .color import NAMED_COLORS, Color
from .state import Mode

_SPEED_NAMES = {"fast": 0x20, "medium": 0x50, "slow": 0x80, "slowest": 0xD0}


def _parse_color(tokens: Sequence[str]) -> Color:
    if len(tokens) == 3:
        try:
            return Color.from_triplet((int(tokens[0]), int(tokens[1]), int(tokens[2])))
        except ValueError as exc:
            raise SystemExit(f"kbcolor: invalid RGB triplet {tokens!r}: {exc}")
    if len(tokens) == 1:
        token = tokens[0].lower()
        if token in NAMED_COLORS:
            return NAMED_COLORS[token]
        try:
            return Color.from_hex(token)
        except ValueError:
            raise SystemExit(
                f"kbcolor: unknown color {tokens[0]!r}. "
                f"Try a name ({', '.join(sorted(NAMED_COLORS))}), '#rrggbb' or 'R G B'.")
    raise SystemExit("kbcolor: expected a color name, '#rrggbb' or three 0-255 values.")


def _parse_speed(value: str) -> int:
    if value.lower() in _SPEED_NAMES:
        return _SPEED_NAMES[value.lower()]
    try:
        speed = int(value, 0)
    except ValueError:
        raise SystemExit(f"kbcolor: invalid speed {value!r} (use fast/medium/slow/slowest or 0-255).")
    if not 0 <= speed <= 255:
        raise SystemExit("kbcolor: speed must be 0-255.")
    return speed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kbcolor", description="Control the keyboard RGB backlight.")
    parser.add_argument("color", nargs="*",
                        help="color name, #rrggbb, 'R G B', or one of: off | rainbow | status")
    parser.add_argument("-b", "--brightness", type=int, default=None,
                        help="brightness level (0..max); defaults to max")
    parser.add_argument("--speed", default="slow", help="rainbow speed: fast/medium/slow/slowest or 0-255")
    parser.add_argument("--off", action="store_true", help="with 'rainbow': disable it")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    backend = SysfsKeyboardBackend()
    if not backend.is_available():
        sys.stderr.write("kbcolor: keyboard backlight not found/writable. Is the driver loaded?\n")
        return 1

    tokens = args.color
    command = tokens[0].lower() if tokens else "status"

    try:
        if command == "status":
            _print_status(backend)
            return 0
        if command == "off":
            backend.set_rainbow(False)
            backend.apply_brightness(0)
            return 0
        if command == "rainbow":
            if args.off:
                backend.set_rainbow(False)
                return 0
            backend.set_rainbow_speed(_parse_speed(args.speed))
            if args.brightness is not None:
                backend.apply_brightness(args.brightness)
            backend.set_rainbow(True)
            return 0

        color = _parse_color(tokens)
        backend.set_rainbow(False)
        backend.apply_color(color)
        backend.apply_brightness(args.brightness if args.brightness is not None else backend.max_brightness)
        print(f"keyboard -> {color.hex}")
        return 0
    except BackendError as exc:
        sys.stderr.write(f"kbcolor: {exc}\n")
        return 1


def _print_status(backend: SysfsKeyboardBackend) -> None:
    state = backend.read_state()
    if state.mode is Mode.RAINBOW:
        print(f"mode: rainbow (speed {state.rainbow_speed})  brightness: {state.brightness}/{backend.max_brightness}")
    else:
        on = "on" if state.is_on else "off"
        print(f"mode: static {state.color.hex} ({on})  brightness: {state.brightness}/{backend.max_brightness}")


if __name__ == "__main__":
    raise SystemExit(main())
