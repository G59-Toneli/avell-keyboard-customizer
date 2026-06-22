"""GUI assembly: wires the reusable widgets to the application controller.

This is the composition root for the desktop app — the only place that knows
about both the concrete backend and the Tk widgets.
"""

from __future__ import annotations

import sys
import tkinter as tk

from . import theme
from .backend import SysfsKeyboardBackend
from .color import Color
from .controller import BacklightController
from .state import BacklightState, Mode
from .widgets import ColorPreview, HueSlider, RoundButton, SaturationValueField, Swatch

PRESETS: tuple[Color, ...] = (
    Color(255, 0, 0), Color(255, 45, 0), Color(255, 150, 0), Color(255, 255, 0),
    Color(0, 255, 0), Color(0, 200, 120), Color(0, 255, 255), Color(0, 120, 255),
    Color(0, 0, 255), Color(140, 0, 255), Color(255, 0, 255), Color(255, 60, 140),
    Color(61, 69, 240), Color(120, 180, 255), Color(255, 170, 80), Color(255, 255, 255),
)

# Firmware rainbow speed byte (higher = slower).
SPEEDS: tuple[tuple[str, int], ...] = (("Fast", 0x20), ("Medium", 0x50), ("Slow", 0x80), ("Slowest", 0xD0))
DEFAULT_SPEED = 0x80

_PREVIEW_ANIM_MS = 55


class KeyboardRGBApp:
    def __init__(self, root: tk.Tk, controller: BacklightController) -> None:
        self._root = root
        self._controller = controller
        self._max_brightness = controller.max_brightness

        state = controller.initial_state
        hue, sat, val = state.color.to_hsv()
        self._hue, self._sat, self._val = hue, sat, val
        self._brightness = state.brightness
        self._rainbow = state.mode is Mode.RAINBOW
        self._speed = state.rainbow_speed or DEFAULT_SPEED
        self._anim_hue = 0.0

        self._build_ui()
        self._sv.render(self._hue)
        self._sv.set_marker(self._sat, self._val)
        self._hue_slider.set_marker(self._hue)
        self._refresh_selection()
        self._update_preview()
        if self._rainbow:
            self._animate_preview()

    # --------------------------------------------------------------- UI assembly
    def _build_ui(self) -> None:
        root = self._root
        root.title("Keyboard RGB")
        root.configure(bg=theme.BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        wrap = tk.Frame(root, bg=theme.BG, padx=theme.PADDING, pady=theme.PADDING)
        wrap.pack()

        header = tk.Frame(wrap, bg=theme.BG)
        header.pack(fill="x")
        tk.Label(header, text="🐸", bg=theme.BG, font=(theme.FONT, 24)).pack(side="left")
        tk.Label(header, text="  Keyboard RGB", bg=theme.BG, fg=theme.TEXT,
                 font=(theme.FONT, 21, "bold")).pack(side="left")
        tk.Label(wrap, text="Avell A62 LIV · drag the field and the slider", bg=theme.BG,
                 fg=theme.TEXT_MUTED, font=(theme.FONT, 11)).pack(anchor="w", pady=(4, 20))

        picker = tk.Frame(wrap, bg=theme.BG)
        picker.pack()
        self._sv = SaturationValueField(picker, on_change=self._on_sv_change)
        self._sv.grid(row=0, column=0)
        self._hue_slider = HueSlider(picker, on_change=self._on_hue_change)
        self._hue_slider.grid(row=0, column=1, padx=(theme.GAP, 0))

        preview_row = tk.Frame(wrap, bg=theme.BG)
        preview_row.pack(fill="x", pady=(20, 2))
        self._preview = ColorPreview(preview_row)
        self._preview.pack(side="left")
        self._hex = tk.Label(preview_row, text="", bg=theme.BG, fg=theme.TEXT,
                             font=(theme.MONO, 20, "bold"))
        self._hex.pack(side="left", padx=18)

        content_width = theme.SV_WIDTH + theme.GAP + theme.HUE_WIDTH

        self._section(wrap, "BRIGHTNESS")
        brightness_row = tk.Frame(wrap, bg=theme.BG)
        brightness_row.pack(fill="x")
        button_w = (content_width - self._max_brightness * 10) // (self._max_brightness + 1)
        self._brightness_buttons: list[RoundButton] = []
        for level in range(self._max_brightness + 1):
            label = "Off" if level == 0 else str(level)
            button = RoundButton(brightness_row, label, lambda lv=level: self._set_brightness(lv), button_w)
            button.grid(row=0, column=level, padx=5)
            self._brightness_buttons.append(button)

        self._section(wrap, "SHORTCUTS")
        shortcuts = tk.Frame(wrap, bg=theme.BG)
        shortcuts.pack()
        for index, color in enumerate(PRESETS):
            Swatch(shortcuts, color, self._set_color).grid(row=index // 8, column=index % 8, padx=5, pady=5)

        actions = tk.Frame(wrap, bg=theme.BG)
        actions.pack(fill="x", pady=(20, 0))
        self._rainbow_button = RoundButton(
            actions, "🌈  Cycle", self._toggle_rainbow, (content_width - 10) * 60 // 100)
        self._rainbow_button.grid(row=0, column=0, padx=(0, 5))
        off_button = RoundButton(actions, "⏻  Off", self._turn_off, (content_width - 10) * 40 // 100)
        off_button.grid(row=0, column=1, padx=(5, 0))

        self._section(wrap, "CYCLE SPEED")
        speed_row = tk.Frame(wrap, bg=theme.BG)
        speed_row.pack(fill="x")
        speed_w = (content_width - 3 * 8) // 4
        self._speed_buttons: dict[int, RoundButton] = {}
        for index, (label, value) in enumerate(SPEEDS):
            button = RoundButton(speed_row, label, lambda v=value: self._set_speed(v), speed_w, height=40)
            button.grid(row=0, column=index, padx=4)
            self._speed_buttons[value] = button

        tk.Label(wrap, text="cycle is a smooth firmware effect · static colors change in ~0.5 s",
                 bg=theme.BG, fg=theme.TEXT_MUTED, font=(theme.FONT, 9), anchor="w").pack(anchor="w", pady=(18, 0))

    def _section(self, parent: tk.Misc, text: str) -> None:
        tk.Label(parent, text=text, bg=theme.BG, fg=theme.TEXT_MUTED,
                 font=(theme.FONT, 9, "bold"), anchor="w").pack(anchor="w", pady=(20, 8))

    # ------------------------------------------------------------------- helpers
    def _current_color(self) -> Color:
        return Color.from_hsv(self._hue, self._sat, self._val)

    def _publish_static(self) -> None:
        self._rainbow = False
        self._refresh_selection()
        self._update_preview()
        self._controller.request(
            BacklightState(Mode.STATIC, self._current_color(), self._brightness, self._speed))

    def _update_preview(self) -> None:
        on = self._brightness > 0
        color = self._current_color()
        self._preview.show(color if on else None)
        self._hex.configure(text=color.hex if on else "OFF")

    def _refresh_selection(self) -> None:
        for level, button in enumerate(self._brightness_buttons):
            button.set_selected(level == self._brightness and not self._rainbow)
        self._rainbow_button.set_selected(self._rainbow)
        for value, button in self._speed_buttons.items():
            button.set_selected(value == self._speed)

    def _ensure_lit(self) -> None:
        if self._brightness == 0:
            self._brightness = self._max_brightness

    # -------------------------------------------------------------------- events
    def _on_sv_change(self, saturation: float, value: float) -> None:
        self._sat, self._val = saturation, value
        self._ensure_lit()
        self._sv.set_marker(saturation, value)
        self._publish_static()

    def _on_hue_change(self, hue: float) -> None:
        self._hue = hue
        self._ensure_lit()
        self._hue_slider.set_marker(hue)
        self._sv.render(hue)
        self._publish_static()

    def _set_color(self, color: Color) -> None:
        self._hue, self._sat, self._val = color.to_hsv()
        self._ensure_lit()
        self._sv.render(self._hue)
        self._sv.set_marker(self._sat, self._val)
        self._hue_slider.set_marker(self._hue)
        self._publish_static()

    def _set_brightness(self, level: int) -> None:
        self._brightness = level
        if self._rainbow and level > 0:
            self._refresh_selection()
            self._controller.request(BacklightState(Mode.RAINBOW, self._current_color(), level, self._speed))
        else:
            self._publish_static()

    def _set_speed(self, value: int) -> None:
        self._speed = value
        self._refresh_selection()
        if self._rainbow:
            self._controller.request(BacklightState(Mode.RAINBOW, self._current_color(), self._brightness, value))

    def _turn_off(self) -> None:
        self._brightness = 0
        self._publish_static()

    def _toggle_rainbow(self) -> None:
        if self._rainbow:
            self._publish_static()  # leaves rainbow, restores the static color
            return
        self._ensure_lit()
        self._rainbow = True
        self._refresh_selection()
        self._controller.request(BacklightState(Mode.RAINBOW, self._current_color(), self._brightness, self._speed))
        self._animate_preview()

    def _animate_preview(self) -> None:
        # Cosmetic only: the firmware does the real cycle; this just shows it's on.
        if not self._rainbow:
            return
        self._anim_hue = (self._anim_hue + 8) % 360
        self._preview.show(Color.from_hsv(self._anim_hue, 1, 1))
        self._hex.configure(text="🌈 cycling")
        self._root.after(_PREVIEW_ANIM_MS, self._animate_preview)

    def _on_close(self) -> None:
        self._controller.stop()
        self._root.destroy()


def main() -> int:
    backend = SysfsKeyboardBackend()
    if not backend.is_available():
        sys.stderr.write(
            "Keyboard backlight not found or not writable at "
            "/sys/class/leds/rgb:kbd_backlight.\n"
            "Is the (patched) tuxedo-drivers module loaded? See the README.\n")
        return 1

    controller = BacklightController(backend)
    controller.start()
    root = tk.Tk()
    KeyboardRGBApp(root, controller)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
