"""Checks that a dimmed window lets the mouse through, and Ctrl brings it back.

    .venv\\Scripts\\python.exe tests\\check_click_through.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cbs import protect, tracker, win32api as w

# Unique per run: a window left behind by a killed run must never be mistaken
# for this one, and they would otherwise all share a title.
TITLE = f"CBS-CLICK-TARGET-{os.getpid()}"
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010

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


def centre_of(hwnd: int) -> tuple[int, int] | None:
    rect = w.window_rect(hwnd)
    if not rect:
        return None
    left, top, right, bottom = rect
    return (left + right) // 2, (top + bottom) // 2


def main() -> int:
    target = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "target_window.py"), TITLE]
    )
    try:
        return run_checks(target)
    finally:
        target.terminate()


def run_checks(target) -> int:
    hwnd = None
    for _ in range(60):
        time.sleep(0.2)
        hwnd = find_target()
        if hwnd:
            break
    if not hwnd:
        print("FAIL: target window never appeared")
        return 1

    # Raise it above everything so hit-testing is unambiguous. TOPMOST works
    # without needing foreground activation rights.
    w.user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    time.sleep(0.5)

    point = centre_of(hwnd)
    print(f"target hwnd = 0x{hwnd:X}  centre = {point}\n")

    check("target receives the mouse to begin with",
          w.window_at_point(*point) == hwnd, f"hit 0x{w.window_at_point(*point):X}")

    print("dim it")
    ok, message = protect.protector.dim(hwnd)
    check("dim reported success", ok, message)
    time.sleep(0.3)

    check("WS_EX_TRANSPARENT applied", bool(w.get_exstyle(hwnd) & w.WS_EX_TRANSPARENT))
    check("WS_EX_LAYERED applied", bool(w.get_exstyle(hwnd) & w.WS_EX_LAYERED))
    check("dim level applied", w.get_alpha(hwnd) == protect.protector.dim_alpha,
          f"alpha={w.get_alpha(hwnd)} expected={protect.protector.dim_alpha}")

    # The limitation, asserted so it can't regress into a false promise: dim is a
    # compositing change, not capture exclusion. A dimmed window is still in every
    # capture stream - which is exactly why it kept showing up in the Meet share.
    # Only the owning process may set WDA_EXCLUDEFROMCAPTURE, so for another app's
    # window there is nothing better available.
    affinity = w.get_display_affinity(hwnd)
    check("dim does NOT exclude from capture, and cannot",
          affinity == w.WDA_NONE, f"affinity={hex(affinity)}")

    print("adjust the transparency")
    protect.protector.set_dim_alpha(80)
    check("alpha applied live to the dimmed window", w.get_alpha(hwnd) == 80,
          f"alpha={w.get_alpha(hwnd)}")
    protect.protector.set_dim_alpha(1000)
    check("clamped to fully opaque", w.get_alpha(hwnd) == 255, f"alpha={w.get_alpha(hwnd)}")
    protect.protector.set_dim_alpha(0)
    check("clamped at the see-through end",
          w.get_alpha(hwnd) == protect.MIN_DIM_ALPHA, f"alpha={w.get_alpha(hwnd)}")
    protect.protector.set_dim_alpha(protect.DEFAULT_DIM_ALPHA)

    beneath = w.window_at_point(*point)
    check("mouse now falls through to what is beneath", beneath != hwnd,
          f"hit 0x{beneath:X}")

    print("hold Ctrl (simulated)")
    protect.protector.set_dimmed_interactive(True)
    time.sleep(0.2)
    check("window takes the mouse again", w.window_at_point(*point) == hwnd,
          f"hit 0x{w.window_at_point(*point):X}")
    check("WS_EX_TRANSPARENT lifted", not w.get_exstyle(hwnd) & w.WS_EX_TRANSPARENT)

    print("release Ctrl (simulated)")
    protect.protector.set_dimmed_interactive(False)
    time.sleep(0.2)
    check("mouse falls through again", w.window_at_point(*point) != hwnd,
          f"hit 0x{w.window_at_point(*point):X}")

    print("un-dim")
    protect.protector.undim(hwnd)
    time.sleep(0.3)
    check("original style restored", not w.get_exstyle(hwnd) & w.WS_EX_TRANSPARENT)
    check("takes the mouse normally again", w.window_at_point(*point) == hwnd,
          f"hit 0x{w.window_at_point(*point):X}")

    print("dim never touches pinning")
    # This test pinned the target itself, so hit-testing was unambiguous. Dimming
    # must leave pinning exactly as it found it, in both directions.
    protect.protector.dim(hwnd)
    time.sleep(0.2)
    check("a pinned window is still pinned while dimmed", w.is_always_on_top(hwnd))
    protect.protector.undim(hwnd)
    check("and still pinned after un-dimming", w.is_always_on_top(hwnd))

    w.set_always_on_top(hwnd, False)
    protect.protector.dim(hwnd)
    time.sleep(0.2)
    check("an unpinned window stays unpinned while dimmed", not w.is_always_on_top(hwnd))
    protect.protector.undim(hwnd)
    check("and still unpinned after un-dimming", not w.is_always_on_top(hwnd))

    print("pinning a single window")
    ok, message = protect.protector.set_pinned(hwnd, True)
    check("pin reported success", ok, message)
    check("window is on top now", w.is_always_on_top(hwnd))
    check("state reports it pinned", protect.protector.state_of(hwnd)["pinned"])

    ok, message = protect.protector.set_pinned(hwnd, False)
    check("un-pin reported success", ok, message)
    check("window is back in the stack", not w.is_always_on_top(hwnd))
    check("state reports it unpinned", not protect.protector.state_of(hwnd)["pinned"])

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
