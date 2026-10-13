"""Ask Windows directly: can we exclude another app's window from capture?

    .venv\\Scripts\\python.exe tools\\probe_capture_exclusion.py [exe-name]

Tries the one API that hides a window from a screen share on a window we do not
own, and prints exactly what Windows says. Also tries our own window, so the
difference is visible side by side.
"""

import ctypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cbs import tracker, win32api as w

WDA = {0: "WDA_NONE", 1: "WDA_MONITOR", 0x11: "WDA_EXCLUDEFROMCAPTURE"}


def attempt(hwnd: int, label: str) -> None:
    ok, err = w.set_display_affinity(hwnd, w.WDA_EXCLUDEFROMCAPTURE)
    now = w.get_display_affinity(hwnd)
    print(f"  target      : {label}")
    print(f"  hwnd        : 0x{hwnd:X}")
    print(f"  call        : SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)")
    print(f"  returned    : {'TRUE (applied)' if ok else 'FALSE (refused)'}")
    if not ok:
        print(f"  GetLastError: {err}  ({ctypes.FormatError(err).strip()})")
    print(f"  affinity now: {WDA.get(now, hex(now) if now >= 0 else 'unreadable')}")
    print()


def main() -> int:
    wanted = (sys.argv[1] if len(sys.argv) > 1 else "chrome.exe").lower()

    theirs = None
    for win in tracker.list_windows():
        if win.exe == wanted:
            theirs = win
            break

    print("Attempting capture exclusion\n")

    if theirs is not None:
        attempt(theirs.hwnd, f"{theirs.exe} - {theirs.title[:56]!r}")
    else:
        print(f"  (no {wanted} window is open - start one and re-run)\n")

    # A window this process creates, for contrast. Needs a real toolkit window,
    # so tkinter; it is destroyed again straight away.
    import tkinter as tk

    root = tk.Tk()
    root.title("cbs-exclusion-probe")
    root.geometry("360x120+80+80")
    tk.Label(root, text="probe window, owned by this process").pack(expand=True)
    root.update()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
    attempt(hwnd, "a window this process owns")
    root.destroy()

    print("Windows requires the window to belong to the calling process.")
    print("There is no flag, style, or privilege that changes that.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
