"""Checks the multi-monitor route: park a window on the other display.

    .venv\\Scripts\\python.exe tests\\check_screens.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cbs import screens, tracker, win32api as w

# Unique per run, so a window left behind by a killed run cannot be mistaken for
# this one's target.
TITLE = f"CBS-SCREEN-TARGET-{os.getpid()}"
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'ok  ' if condition else 'FAIL'}] {label}{f' - {detail}' if detail else ''}")
    if not condition:
        failures.append(label)


def find_target() -> int | None:
    for win in tracker.list_windows():
        if win.title == TITLE:
            return win.hwnd
    return None


def on_monitor(hwnd: int) -> str:
    handle = screens.monitor_of(hwnd)
    for monitor in screens.list_monitors():
        if monitor["handle"] == handle:
            return monitor["label"]
    return "<unknown>"


def main() -> int:
    monitors = screens.list_monitors()
    print(f"monitors: {[m['label'] for m in monitors]}\n")
    if len(monitors) < 2:
        print("SKIP: needs at least two monitors")
        return 0

    target = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "target_window.py"), TITLE]
    )
    try:
        return run_checks(monitors)
    finally:
        target.terminate()


def run_checks(monitors) -> int:
    hwnd = None
    for _ in range(60):
        time.sleep(0.2)
        hwnd = find_target()
        if hwnd:
            break
    if not hwnd:
        print("FAIL: target window never appeared")
        return 1

    print(f"target hwnd = 0x{hwnd:X}")
    start = on_monitor(hwnd)
    print(f"starts on   : {start}\n")

    print("move to the other monitor")
    ok, message = screens.move_to_other_monitor(hwnd)
    check("reported success", ok, message)
    time.sleep(0.4)

    moved = on_monitor(hwnd)
    check("now on a different monitor", moved != start, moved)

    rect = w.window_rect(hwnd)
    handle = screens.monitor_of(hwnd)
    bounds = next(m["rect"] for m in monitors if m["handle"] == handle)
    if rect:
        left, top, right, bottom = rect
        inside = left >= bounds[0] and top >= bounds[1] and right <= bounds[2] and bottom <= bounds[3]
        check("window rect sits inside the target display", inside, f"rect={rect} bounds={bounds}")
    else:
        check("window rect readable", False)

    print("\nmove back")
    ok, message = screens.move_to_other_monitor(hwnd)
    check("reported success", ok, message)
    time.sleep(0.4)
    check("returned to the original monitor", on_monitor(hwnd) == start, on_monitor(hwnd))

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
