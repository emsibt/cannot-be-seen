"""Render the logo assets from docs/logo.svg.

    .venv\\Scripts\\python.exe tools\\render_logo.py

Writes docs/logo.png (for the README) and cbs/assets/icon.png (the tray icon) so
both come from the same vector source and cannot drift apart.

Headless Edge is the renderer because the mark relies on an SVG mask to punch the
slash out of the eye, which Pillow cannot do.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "docs" / "logo.svg"

TARGETS = [
    (ROOT / "docs" / "logo.png", 512),
    (ROOT / "cbs" / "assets" / "icon.png", 64),
]

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  img {{ display: block; width: {size}px; height: {size}px; }}
</style></head><body><img src="{uri}" alt=""></body></html>"""


def find_browser() -> str | None:
    for path in BROWSERS:
        if Path(path).exists():
            return path
    return None


def render(browser: str, size: int, out: Path) -> bool:
    staged = ROOT / f"_logo_{size}.html"
    staged.write_text(
        HTML.format(size=size, uri=SVG.as_uri()), encoding="utf-8"
    )
    out.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             "--default-background-color=00000000",
             f"--user-data-dir={profile}",
             "--force-device-scale-factor=1", "--virtual-time-budget=1200",
             f"--window-size={size},{size}", f"--screenshot={out}", staged.as_uri()],
            check=False, timeout=90,
        )
    staged.unlink(missing_ok=True)
    return out.exists()


def main() -> int:
    browser = find_browser()
    if not browser:
        print("no Edge or Chrome found")
        return 1
    if not SVG.exists():
        print(f"missing {SVG}")
        return 1

    failed = False
    for out, size in TARGETS:
        ok = render(browser, size, out)
        print(f"{'wrote' if ok else 'FAILED'} {out.relative_to(ROOT)} ({size}x{size})")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
