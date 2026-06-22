"""Design tokens for the GUI (colors, radii, fonts, geometry).

Keeping these in one place makes the look consistent and easy to retheme without
touching widget logic.
"""

from __future__ import annotations

# Palette (dark)
BG = "#0e0f13"
SURFACE = "#1b1f29"
SURFACE_HOVER = "#262c3a"
TEXT = "#eef0f5"
TEXT_MUTED = "#7e8597"
ACCENT = "#3d45f0"
OUTLINE = "#39414f"

# Geometry
SV_WIDTH, SV_HEIGHT = 480, 320          # saturation/value field
SV_RENDER_W, SV_RENDER_H = 240, 160     # rendered at half-res, then zoomed x2
HUE_WIDTH, HUE_HEIGHT = 56, 320         # vertical hue slider
CORNER_RADIUS = 22
HUE_CORNER_RADIUS = 16
PADDING = 28
GAP = 18

# Fonts
FONT = "Sans"
MONO = "Monospace"
