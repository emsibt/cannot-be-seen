"""Checks a protected window gets its navigation bar, stays excluded, and that
exclusion lands on the right window when another of ours opens at the same time.

    .venv\\Scripts\\python.exe tests\\check_browser.py
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import webview

from cbs import browser, tracker, win32api as w

TAB_ID = "check"
TITLE = "cbs-browser-check"
# Deliberately sorts before TITLE: windows are enumerated in title order, so this
# is what the racy before/after diff would have grabbed first. It mirrors the app,
# where the dashboard ("cannot-be-seen") sorts before a protected window's label.
DECOY_TITLE = "cbs-browser-aaa"

DECOY_HTML = f"<html><head><title>{DECOY_TITLE}</title></head><body>decoy</body></html>"

failures: list[str] = []
protected = browser.ProtectedWindows()
exit_code = 1


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}{f' - {detail}' if detail else ''}")
    if not condition:
        failures.append(label)


def find_by_title(title: str) -> int | None:
    for win in tracker.list_windows():
        if win.title == title:
            return win.hwnd
    return None


def monitor() -> None:
    global exit_code

    item = None
    deadline = time.time() + 25
    while time.time() < deadline:
        item = next((p for p in protected.list() if p["id"] == TAB_ID), None)
        if item and item["hwnd"] and not item["status"].startswith("opening"):
            break
        time.sleep(0.25)

    if not item or not item["hwnd"]:
        check("protected window was claimed", False)
        protected.close(TAB_ID)
        exit_code = 1
        return

    time.sleep(2.0)  # let the loaded handler inject
    record = protected._items.get(TAB_ID)
    window = record["window"]
    print(f"protected hwnd = 0x{item['hwnd']:X}\n")

    affinity = w.get_display_affinity(item["hwnd"])
    check("protected window is excluded from capture",
          affinity == w.WDA_EXCLUDEFROMCAPTURE, hex(affinity))

    # The regression: the decoy opened at the same moment, before the ui loop
    # was running, so a before/after diff could claim it instead.
    decoy = find_by_title(DECOY_TITLE)
    if decoy:
        decoy_affinity = w.get_display_affinity(decoy)
        check("the other window was NOT protected", decoy_affinity != w.WDA_EXCLUDEFROMCAPTURE,
              hex(decoy_affinity))
        check("the two windows are different", decoy != item["hwnd"])
    else:
        check("decoy window found", False, "could not locate it")

    has_bar = window.evaluate_js("!!document.getElementById('__cbs_toolbar')")
    check("navigation bar injected", bool(has_bar))

    has_address = window.evaluate_js("!!document.querySelector('#__cbs_toolbar input')")
    check("address bar present", bool(has_address))

    buttons = window.evaluate_js("document.querySelectorAll('#__cbs_toolbar button').length")
    check("navigation buttons present", (buttons or 0) >= 5, f"{buttons} found")

    bridge = window.evaluate_js("!!(window.pywebview && window.pywebview.api)")
    check("bridge exposed to the page", bool(bridge))

    api = window.evaluate_js("Object.keys(window.pywebview.api).join(',')")
    check("bridge exposes new_window/close_window", "new_window" in (api or ""), api)

    print("\nholding open for 5s")
    time.sleep(5)

    exit_code = 1 if failures else 0
    protected.close(TAB_ID)
    for open_window in list(webview.windows):
        try:
            open_window.destroy()
        except Exception:
            pass


def main() -> int:
    threading.Thread(target=monitor, daemon=True).start()

    # Both before start(), exactly as the app does it: the dashboard and any
    # saved protected tabs appear together.
    webview.create_window(DECOY_TITLE, html=DECOY_HTML, width=420, height=260)
    protected.open(TAB_ID, TITLE, "https://example.com")
    webview.start(gui="edgechromium")

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
