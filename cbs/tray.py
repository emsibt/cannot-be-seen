"""Tray icon and its menu.

The icon is rendered from docs/logo.svg by tools/render_logo.py, so the tray and
the project logo cannot drift apart.
"""

from pathlib import Path

import pystray
from PIL import Image, ImageDraw

ICON_PATH = Path(__file__).parent / "assets" / "icon.png"


def _fallback_image(size: int = 64) -> Image.Image:
    """Only used if the rendered asset is missing."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        [size * 0.05, size * 0.05, size * 0.95, size * 0.95],
        radius=size * 0.22,
        fill=(31, 111, 235, 255),
    )
    draw.line(
        [size * 0.3, size * 0.72, size * 0.7, size * 0.28],
        fill=(255, 255, 255, 255),
        width=max(2, size // 7),
    )
    return image


def build_icon_image() -> Image.Image:
    try:
        return Image.open(ICON_PATH).convert("RGBA")
    except OSError:
        return _fallback_image()


def build_icon(handlers: dict) -> pystray.Icon:
    """handlers: dashboard, new_window, show_all, toggle_dashboard, quit"""
    menu = pystray.Menu(
        pystray.MenuItem("Open dashboard", handlers["dashboard"], default=True),
        pystray.MenuItem("New protected window", handlers["new_window"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Show all hidden windows", handlers["show_all"]),
        pystray.MenuItem(
            "Exclude dashboard from capture",
            handlers["toggle_dashboard"],
            checked=lambda item: handlers["dashboard_protected"](),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", handlers["quit"]),
    )
    return pystray.Icon("cannot-be-seen", build_icon_image(), "cannot-be-seen", menu)
