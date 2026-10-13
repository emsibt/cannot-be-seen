"""Multi-monitor helpers.

Teams and Meet share one monitor when you pick "entire screen". Anything parked
on a display you are not sharing is therefore never captured, which makes a
second monitor the only reliable way to keep a window *you can still read and
type in* out of a share when the window belongs to another app.
"""

import ctypes

from . import win32api as w


def list_monitors() -> list[dict]:
    """Connected monitors, left to right, each with a stable display name."""
    found: list[dict] = []

    def callback(hmonitor, _hdc, _rect, _data):
        info = w.MONITORINFO()
        info.cbSize = ctypes.sizeof(w.MONITORINFO)
        if w.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            found.append(
                {
                    "handle": int(hmonitor),
                    "rect": (
                        info.rcMonitor.left,
                        info.rcMonitor.top,
                        info.rcMonitor.right,
                        info.rcMonitor.bottom,
                    ),
                    "work": (
                        info.rcWork.left,
                        info.rcWork.top,
                        info.rcWork.right,
                        info.rcWork.bottom,
                    ),
                    "primary": bool(info.dwFlags & w.MONITORINFOF_PRIMARY),
                }
            )
        return True

    w.user32.EnumDisplayMonitors(None, None, w.MonitorEnumProc(callback), 0)
    found.sort(key=lambda m: (m["rect"][0], m["rect"][1]))
    for index, monitor in enumerate(found, start=1):
        left, top, right, bottom = monitor["rect"]
        monitor["name"] = f"screen {index}"
        monitor["label"] = f"screen {index} ({right - left}×{bottom - top})"
    return found


def monitor_of(hwnd: int) -> int:
    return int(w.user32.MonitorFromWindow(hwnd, w.MONITOR_DEFAULTTONEAREST))


def move_to_other_monitor(hwnd: int) -> tuple[bool, str]:
    """Move a window onto a display that isn't the one it currently sits on.

    Prefers a non-primary display, on the assumption that the primary one is the
    one being shared.
    """
    monitors = list_monitors()
    if len(monitors) < 2:
        return False, "only one monitor is connected"
    if not w.is_alive(hwnd):
        return False, "window is gone"

    hwnd = w.top_level(hwnd)
    current = monitor_of(hwnd)
    others = [m for m in monitors if m["handle"] != current]
    if not others:
        return False, "could not work out which monitor this window is on"
    target = next((m for m in others if not m["primary"]), others[0])

    rect = w.window_rect(hwnd)
    if rect is None:
        return False, "could not read the window position"
    left, top, right, bottom = rect
    width, height = right - left, bottom - top

    work_left, work_top, work_right, work_bottom = target["work"]
    work_width = work_right - work_left
    work_height = work_bottom - work_top

    if width > work_width:
        x = work_left
    else:
        x = work_left + (work_width - width) // 2
    if height > work_height:
        y = work_top
    else:
        y = work_top + (work_height - height) // 2

    if w.is_maximized(hwnd) or w.user32.IsIconic(hwnd):
        w.user32.ShowWindow(hwnd, w.SW_RESTORE)

    moved = w.user32.SetWindowPos(
        hwnd, None, x, y, width, height, w.SWP_NOZORDER | w.SWP_NOACTIVATE
    )
    if not moved:
        return False, "Windows refused to move the window"
    return True, f"moved to {target['label']}"
