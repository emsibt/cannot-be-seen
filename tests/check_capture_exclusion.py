"""End-to-end check: is a protected window really excluded from capture?

Opens one protected window, lets the app's own claiming logic run, then reads
the window's display affinity back with an independent API call.

    .venv\\Scripts\\python.exe tests\\check_capture_exclusion.py
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview

from cbs import browser, win32api as w

TITLE = "cbs-exclusion-check"
TAB_ID = "check"
HOLD_SECONDS = 6

protected = browser.ProtectedWindows()
exit_code = 1


def report() -> int:
    item = next((p for p in protected.list() if p["id"] == TAB_ID), None)
    if not item:
        print("FAIL: the window was never registered")
        return 1

    print(f"claim status : {item['status']}")
    hwnd = item["hwnd"]
    if not hwnd:
        print("FAIL: no window handle was resolved")
        return 1

    affinity = w.get_display_affinity(hwnd)
    print(f"hwnd         : 0x{hwnd:X}")
    print(f"affinity     : {hex(affinity)}")

    if affinity != w.WDA_EXCLUDEFROMCAPTURE:
        print("\nFAIL: window is NOT excluded from capture")
        return 1

    print("\nPASS: window is excluded from screen capture")
    print("      visible on screen, absent from every capture API")
    return 0


def monitor() -> None:
    global exit_code
    deadline = time.time() + 20
    while time.time() < deadline:
        item = next((p for p in protected.list() if p["id"] == TAB_ID), None)
        if item and item["hwnd"] and not item["status"].startswith("opening"):
            break
        time.sleep(0.25)

    time.sleep(0.75)
    exit_code = report()

    print(f"\nholding the window open for {HOLD_SECONDS}s - try Win+Shift+S now")
    time.sleep(HOLD_SECONDS)
    protected.close(TAB_ID)


def main() -> int:
    threading.Thread(target=monitor, daemon=True).start()
    protected.open(TAB_ID, TITLE, "https://example.com")
    webview.start(gui="edgechromium")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
