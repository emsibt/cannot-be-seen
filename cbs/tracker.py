"""Enumeration of on-screen top-level windows."""

from dataclasses import dataclass, asdict

from . import win32api as w

_current_pid = w.kernel32.GetCurrentProcessId()


@dataclass(frozen=True)
class Window:
    hwnd: int
    title: str
    exe: str
    pid: int
    cls: str
    ours: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _is_worth_listing(hwnd: int) -> bool:
    if not w.user32.IsWindowVisible(hwnd):
        return False
    if w.user32.GetWindowTextLengthW(hwnd) <= 0:
        return False
    if w.is_cloaked(hwnd):
        return False
    # Tool windows with an owner are almost always invisible scaffolding.
    style = w.get_exstyle(hwnd)
    if style & w.WS_EX_TOOLWINDOW and not style & w.WS_EX_APPWINDOW:
        if w.user32.GetWindow(hwnd, 4):  # GW_OWNER
            return False
    return True


def list_windows() -> list[Window]:
    """Every visible, titled, non-cloaked top-level window on the desktop."""
    found: list[Window] = []

    def callback(hwnd, _lparam):
        if _is_worth_listing(hwnd):
            pid = w.window_pid(hwnd)
            found.append(
                Window(
                    hwnd=hwnd,
                    title=w.window_title(hwnd),
                    exe=w.process_name(pid),
                    pid=pid,
                    cls=w.window_class(hwnd),
                    ours=pid == _current_pid,
                )
            )
        return True

    w.user32.EnumWindows(w.EnumWindowsProc(callback), 0)
    found.sort(key=lambda win: (win.exe, win.title.lower()))
    return found


def list_own_windows() -> list[Window]:
    return [win for win in list_windows() if win.ours]
