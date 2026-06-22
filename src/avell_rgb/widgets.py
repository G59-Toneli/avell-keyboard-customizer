"""Reusable, framework-only Tk canvas widgets.

These are pure presentation components: they draw themselves and emit normalized
values through callbacks. They know nothing about the keyboard or the
controller, so they could be reused in any Tk project.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

from . import theme
from .color import Color

__all__ = ["RoundButton", "Swatch", "ColorPreview", "SaturationValueField", "HueSlider"]


def _rounded_polygon(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int, **kw) -> int:
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


def _corner_pixels(width: int, height: int, radius: int) -> list[tuple[int, int]]:
    """Pixels in each corner that fall outside the rounding radius (made
    transparent to fake rounded image corners)."""
    pixels: list[tuple[int, int]] = []
    for dx in range(radius):
        for dy in range(radius):
            if (dx - radius) ** 2 + (dy - radius) ** 2 > radius * radius:
                pixels += [
                    (dx, dy),
                    (width - 1 - dx, dy),
                    (dx, height - 1 - dy),
                    (width - 1 - dx, height - 1 - dy),
                ]
    return pixels


class RoundButton(tk.Canvas):
    """A flat, rounded, optionally-selectable button with a hover state."""

    def __init__(self, parent: tk.Misc, text: str, command: Callable[[], None],
                 width: int, height: int = 40, radius: int = 13,
                 font: tuple = (theme.FONT, 11, "bold")) -> None:
        super().__init__(parent, width=width, height=height, bg=theme.BG,
                         highlightthickness=0, bd=0, cursor="hand2")
        # NOTE: do not use self._w / self._h — tkinter.Canvas reserves self._w
        # for the widget's Tk path name.
        self._text, self._command = text, command
        self._width, self._height, self._radius, self._font = width, height, radius, font
        self._selected = self._hover = False
        self.bind("<Button-1>", lambda _e: self._command())
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        self._draw()

    def set_selected(self, selected: bool) -> None:
        if selected != self._selected:
            self._selected = selected
            self._draw()

    def _set_hover(self, hover: bool) -> None:
        self._hover = hover
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        fill = theme.ACCENT if self._selected else (theme.SURFACE_HOVER if self._hover else theme.SURFACE)
        _rounded_polygon(self, 2, 2, self._width - 2, self._height - 2, self._radius, fill=fill, outline="")
        self.create_text(self._width / 2, self._height / 2, text=self._text,
                         fill="#ffffff" if self._selected else theme.TEXT, font=self._font)


class Swatch(tk.Canvas):
    """A clickable rounded color chip used for preset shortcuts."""

    def __init__(self, parent: tk.Misc, color: Color, command: Callable[[Color], None],
                 size: int = 60, radius: int = 16) -> None:
        super().__init__(parent, width=size, height=size, bg=theme.BG,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._color, self._command = color, command
        self._size, self._radius = size, radius
        self.bind("<Button-1>", lambda _e: self._command(self._color))
        self.bind("<Enter>", lambda _e: self._draw(hover=True))
        self.bind("<Leave>", lambda _e: self._draw(hover=False))
        self._draw(hover=False)

    def _draw(self, *, hover: bool) -> None:
        self.delete("all")
        if hover:
            _rounded_polygon(self, 1, 1, self._size - 1, self._size - 1, self._radius + 1,
                             fill=self._color.hex, outline="#ffffff", width=2)
        else:
            _rounded_polygon(self, 4, 4, self._size - 4, self._size - 4, self._radius,
                             fill=self._color.hex, outline="")


class ColorPreview(tk.Canvas):
    """A rounded chip that displays the currently selected color."""

    def __init__(self, parent: tk.Misc, width: int = 96, height: int = 52) -> None:
        super().__init__(parent, width=width, height=height, bg=theme.BG,
                         highlightthickness=0, bd=0)
        self._chip = _rounded_polygon(self, 1, 1, width - 1, height - 1, 15,
                                      fill="#000000", outline=theme.OUTLINE)

    def show(self, color: Color | None) -> None:
        self.itemconfig(self._chip, fill=color.hex if color else "#000000")


class SaturationValueField(tk.Canvas):
    """The 2D saturation (x) / value (y) field of a color picker.

    Rendered at half resolution and zoomed x2 to stay responsive while dragging
    the hue. Emits ``(saturation, value)`` in [0, 1] through ``on_change``.
    """

    def __init__(self, parent: tk.Misc, on_change: Callable[[float, float], None]) -> None:
        super().__init__(parent, width=theme.SV_WIDTH, height=theme.SV_HEIGHT,
                         bg=theme.BG, highlightthickness=0, bd=0, cursor="crosshair")
        self._on_change = on_change
        self._corners = _corner_pixels(theme.SV_WIDTH, theme.SV_HEIGHT, theme.CORNER_RADIUS)
        self._base = tk.PhotoImage(width=theme.SV_RENDER_W, height=theme.SV_RENDER_H)
        self._display = self._base.zoom(2)
        self._image_item = self.create_image(0, 0, anchor="nw", image=self._display)
        _rounded_polygon(self, 1, 1, theme.SV_WIDTH - 1, theme.SV_HEIGHT - 1,
                         theme.CORNER_RADIUS, outline=theme.OUTLINE, width=1, fill="")
        self._marker_outer = self.create_oval(0, 0, 0, 0, outline="#000000", width=6)
        self._marker_inner = self.create_oval(0, 0, 0, 0, outline="#ffffff", width=3)
        for event in ("<Button-1>", "<B1-Motion>"):
            self.bind(event, self._on_pointer)

    def render(self, hue: float) -> None:
        """Repaint the gradient for the given hue (degrees)."""
        hue_color = Color.from_hsv(hue, 1.0, 1.0)
        hr, hg, hb = hue_color.as_triplet
        columns = []
        for i in range(theme.SV_RENDER_W):
            s = i / (theme.SV_RENDER_W - 1)
            inv = 1 - s
            columns.append((255 * inv, hr * s, hg * s, hb * s))
        rows = []
        for j in range(theme.SV_RENDER_H):
            v = 1 - j / (theme.SV_RENDER_H - 1)
            rows.append("{" + " ".join(
                "#%02x%02x%02x" % (int(v * (w + rs)), int(v * (w + gs)), int(v * (w + bs)))
                for (w, rs, gs, bs) in columns) + "}")
        self._base.put(" ".join(rows))
        self._display = self._base.zoom(2)
        for x, y in self._corners:
            self._display.transparency_set(x, y, True)
        self.itemconfig(self._image_item, image=self._display)

    def set_marker(self, saturation: float, value: float) -> None:
        x = saturation * theme.SV_WIDTH
        y = (1 - value) * theme.SV_HEIGHT
        for marker in (self._marker_outer, self._marker_inner):
            self.coords(marker, x - 11, y - 11, x + 11, y + 11)

    def _on_pointer(self, event: tk.Event) -> None:
        s = min(1.0, max(0.0, event.x / theme.SV_WIDTH))
        v = 1.0 - min(1.0, max(0.0, event.y / theme.SV_HEIGHT))
        self._on_change(s, v)


class HueSlider(tk.Canvas):
    """A vertical hue bar. Emits the hue in degrees [0, 360) through ``on_change``."""

    def __init__(self, parent: tk.Misc, on_change: Callable[[float], None]) -> None:
        super().__init__(parent, width=theme.HUE_WIDTH, height=theme.HUE_HEIGHT,
                         bg=theme.BG, highlightthickness=0, bd=0, cursor="sb_v_double_arrow")
        self._on_change = on_change
        self._image = tk.PhotoImage(width=theme.HUE_WIDTH, height=theme.HUE_HEIGHT)
        self.create_image(0, 0, anchor="nw", image=self._image)
        _rounded_polygon(self, 1, 1, theme.HUE_WIDTH - 1, theme.HUE_HEIGHT - 1,
                         theme.HUE_CORNER_RADIUS, outline=theme.OUTLINE, width=1, fill="")
        self._marker_outer = self.create_rectangle(0, 0, 0, 0, outline="#000000", width=6)
        self._marker_inner = self.create_rectangle(0, 0, 0, 0, outline="#ffffff", width=3)
        self._render()
        for event in ("<Button-1>", "<B1-Motion>"):
            self.bind(event, self._on_pointer)

    def set_marker(self, hue: float) -> None:
        y = hue / 360.0 * theme.HUE_HEIGHT
        for marker in (self._marker_outer, self._marker_inner):
            self.coords(marker, 1, y - 8, theme.HUE_WIDTH - 1, y + 8)

    def _render(self) -> None:
        def hue_row(j: int) -> str:
            cell = "#%02x%02x%02x" % Color.from_hsv(j / (theme.HUE_HEIGHT - 1) * 360, 1, 1).as_triplet
            return "{" + " ".join([cell] * theme.HUE_WIDTH) + "}"

        rows = [hue_row(j) for j in range(theme.HUE_HEIGHT)]
        self._image.put(" ".join(rows))
        for x, y in _corner_pixels(theme.HUE_WIDTH, theme.HUE_HEIGHT, theme.HUE_CORNER_RADIUS):
            self._image.transparency_set(x, y, True)

    def _on_pointer(self, event: tk.Event) -> None:
        hue = min(1.0, max(0.0, event.y / theme.HUE_HEIGHT)) * 360.0
        self._on_change(hue)
