"""Raw Win32 bindings used by the rest of the app.

Everything here is plain ctypes so the app has no native build step.
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

# --- constants ---------------------------------------------------------------

GWL_EXSTYLE = -20
GWL_STYLE = -16

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

VK_CONTROL = 0x11

LWA_ALPHA = 0x00000002

WDA_NONE = 0x00000000
WDA_MONITOR = 0x00000001
WDA_EXCLUDEFROMCAPTURE = 0x00000011

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOW = 5
SW_RESTORE = 9

DWMWA_CLOAKED = 14

GA_ROOT = 2

MONITOR_DEFAULTTONEAREST = 2
MONITORINFOF_PRIMARY = 0x00000001

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

ERROR_ACCESS_DENIED = 5

# --- bindings ----------------------------------------------------------------

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HANDLE,          # HMONITOR
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    wintypes.LPARAM,
)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


user32.WindowFromPoint.argtypes = [POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_ushort


user32.EnumDisplayMonitors.argtypes = [
    wintypes.HDC,
    ctypes.POINTER(wintypes.RECT),
    MonitorEnumProc,
    wintypes.LPARAM,
]
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HANDLE
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.IsZoomed.restype = wintypes.BOOL

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
user32.GetWindowDisplayAffinity.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowDisplayAffinity.restype = wintypes.BOOL

user32.SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_ubyte,
    wintypes.DWORD,
]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.GetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.POINTER(wintypes.DWORD),
]
user32.GetLayeredWindowAttributes.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

_GetWindowLongPtr = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_SetWindowLongPtr = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
_GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
_GetWindowLongPtr.restype = ctypes.c_ssize_t
_SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
_SetWindowLongPtr.restype = ctypes.c_ssize_t

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetCurrentProcessId.argtypes = []
kernel32.GetCurrentProcessId.restype = wintypes.DWORD

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD,
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


# --- helpers -----------------------------------------------------------------

_exe_cache: dict[int, str] = {}


def window_title(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_path(pid: int) -> str:
    """Full image path for a pid, or "" if it can't be read."""
    cached = _exe_cache.get(pid)
    if cached is not None:
        return cached

    path = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                path = buf.value
        finally:
            kernel32.CloseHandle(handle)

    if path:
        _exe_cache[pid] = path
    return path


def process_name(pid: int) -> str:
    path = process_path(pid)
    return path.rsplit("\\", 1)[-1].lower() if path else ""


def is_cloaked(hwnd: int) -> bool:
    """Cloaked windows are alive but not really on screen (suspended UWP etc.)."""
    value = wintypes.DWORD()
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
    )
    return hr == 0 and value.value != 0


def is_alive(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd))


def top_level(hwnd: int) -> int:
    """Nearest top-level ancestor. SetWindowDisplayAffinity only accepts these."""
    root = user32.GetAncestor(hwnd, GA_ROOT)
    return root or hwnd


def window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def is_maximized(hwnd: int) -> bool:
    return bool(user32.IsZoomed(hwnd))


def get_exstyle(hwnd: int) -> int:
    return _GetWindowLongPtr(hwnd, GWL_EXSTYLE)


def set_exstyle(hwnd: int, value: int) -> bool:
    ctypes.set_last_error(0)
    _SetWindowLongPtr(hwnd, GWL_EXSTYLE, value)
    return ctypes.get_last_error() == 0


def set_alpha(hwnd: int, alpha: int) -> bool:
    """Make a window translucent. Works cross-process; purely cosmetic.

    Not a privacy feature - a translucent window is still fully captured.
    """
    style = get_exstyle(hwnd)
    if not style & WS_EX_LAYERED:
        set_exstyle(hwnd, style | WS_EX_LAYERED)
    ctypes.set_last_error(0)
    ok = user32.SetLayeredWindowAttributes(hwnd, 0, max(0, min(255, alpha)), LWA_ALPHA)
    return bool(ok)


def set_click_through(hwnd: int, enabled: bool) -> bool:
    """Let the mouse fall through the window to whatever is beneath it.

    WS_EX_TRANSPARENT is what makes a window invisible to hit-testing, and it
    needs WS_EX_LAYERED alongside it to behave. Works cross-process.
    """
    style = get_exstyle(hwnd)
    if enabled:
        updated = style | WS_EX_LAYERED | WS_EX_TRANSPARENT
    else:
        updated = style & ~WS_EX_TRANSPARENT
    if updated == style:
        return True
    return set_exstyle(hwnd, updated)


def clear_alpha(hwnd: int) -> bool:
    if not is_alive(hwnd):
        return False
    style = get_exstyle(hwnd)
    user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
    updated = style & ~(WS_EX_LAYERED | WS_EX_TRANSPARENT)
    if updated != style:
        set_exstyle(hwnd, updated)
    return True


def restore_exstyle(hwnd: int, exstyle: int) -> bool:
    """Put the extended style back exactly as it was before we touched it."""
    if not is_alive(hwnd):
        return False
    return set_exstyle(hwnd, exstyle)


def get_alpha(hwnd: int) -> int | None:
    """Current translucency of a layered window, or None if it is not layered."""
    key = wintypes.DWORD()
    alpha = ctypes.c_ubyte()
    flags = wintypes.DWORD()
    ok = user32.GetLayeredWindowAttributes(
        hwnd, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(flags)
    )
    return alpha.value if ok else None


def is_always_on_top(hwnd: int) -> bool:
    return bool(get_exstyle(hwnd) & WS_EX_TOPMOST)


def set_always_on_top(hwnd: int, enabled: bool) -> bool:
    """Pin a window above everything else, or let it fall back into the stack.

    Works cross-process. SWP_NOACTIVATE keeps the window from stealing focus as
    it is raised, which would otherwise yank you out of whatever you are doing.
    """
    if not is_alive(hwnd):
        return False
    return bool(
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST if enabled else HWND_NOTOPMOST,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    )


def window_at_point(x: int, y: int) -> int:
    """Top-level window that would receive a click at this screen point.

    Returns 0 when the point is not over one of our windows' top levels.
    """
    hwnd = user32.WindowFromPoint(POINT(x, y))
    return top_level(hwnd) if hwnd else 0


def ctrl_is_down() -> bool:
    return bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)


def set_display_affinity(hwnd: int, affinity: int = WDA_EXCLUDEFROMCAPTURE) -> tuple[bool, int]:
    """Returns (ok, last_error).

    Windows only permits this on a window owned by the calling process; any
    other window fails with ERROR_ACCESS_DENIED.
    """
    ctypes.set_last_error(0)
    ok = user32.SetWindowDisplayAffinity(hwnd, affinity)
    return bool(ok), ctypes.get_last_error()


def get_display_affinity(hwnd: int) -> int:
    value = wintypes.DWORD()
    if user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(value)):
        return value.value
    return -1


def hide_window(hwnd: int) -> bool:
    return bool(user32.ShowWindow(hwnd, SW_HIDE))


def show_window(hwnd: int, restore: bool = False) -> bool:
    return bool(user32.ShowWindow(hwnd, SW_RESTORE if restore else SW_SHOW))
