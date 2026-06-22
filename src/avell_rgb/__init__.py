"""avell_rgb — control the single-zone RGB keyboard backlight of Avell (Uniwill) laptops.

Layers (dependencies point inward):

    color / state            domain value objects (pure)
        ^
    backend                  port + sysfs adapter (hardware isolation)
        ^
    controller               application service (async, coalescing)
        ^
    widgets / app / cli      presentation / entry points
"""

from __future__ import annotations

__version__ = "1.0.0"

__all__ = ["__version__"]
