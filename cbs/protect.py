"""Applies the available protection modes to individual windows.

Two very different things live here, and the difference matters:

* ``exclude_from_capture`` is real protection - the window stays fully visible
  to you but is absent from every screen-capture API. Windows enforces that a
  process may only set this on a window it owns, so it works for the windows
  this app creates and nothing else.

* ``dim`` and ``hide`` work on any window because they are ordinary window
  manipulations. Neither one hides a window from capture while you are still
  reading it: ``dim`` leaves the pixels captured (just fainter), and ``hide``
  removes the window from the screen altogether.
"""

from . import win32api as w

DEFAULT_DIM_ALPHA = 140
MIN_DIM_ALPHA = 25


class Protector:
    def __init__(self) -> None:
        # hwnd -> the rule that dimmed it, or None when dimmed by hand. The
        # watcher only releases the ones it applied, so a manual dim sticks.
        self._dimmed: dict[int, str | None] = {}
        self._dim_restore: dict[int, int] = {}    # hwnd -> extended style before we touched it
        self._pinned: set[int] = set()            # windows we raised on the user's behalf
        self._dimmed_interactive = False
        self.dim_alpha = DEFAULT_DIM_ALPHA
        self._hidden: dict[int, str | None] = {}  # hwnd -> rule id that hid it
        self._hidden_meta: dict[int, dict] = {}   # hwnd -> {title, exe} for display

    # -- queries ------------------------------------------------------------

    def state_of(self, hwnd: int) -> dict:
        self._prune()
        alive = w.is_alive(hwnd)
        affinity = w.get_display_affinity(hwnd) if alive else -1
        return {
            "dimmed": hwnd in self._dimmed,
            "hidden": hwnd in self._hidden,
            "capture_excluded": affinity == w.WDA_EXCLUDEFROMCAPTURE,
            "visible": bool(w.user32.IsWindowVisible(hwnd)) if alive else False,
            "pinned": hwnd in self._pinned and alive,
        }

    @property
    def hidden(self) -> list[dict]:
        self._prune()
        return [
            {"hwnd": hwnd, "rule_id": self._hidden[hwnd], **self._hidden_meta.get(hwnd, {})}
            for hwnd in self._hidden
        ]

    @staticmethod
    def can_exclude(hwnd: int) -> tuple[bool, str]:
        """Whether capture exclusion is even attemptable for this window."""
        if not w.is_alive(hwnd):
            return False, "window is gone"
        hwnd = w.top_level(hwnd)
        pid = w.window_pid(hwnd)
        if pid != w.kernel32.GetCurrentProcessId():
            return (
                False,
                "Windows only allows capture exclusion on a window owned by the "
                "calling process, so this cannot be applied to another app's window",
            )
        return True, ""

    # -- capture exclusion (real protection) --------------------------------

    def exclude_from_capture(self, hwnd: int) -> tuple[bool, str]:
        if not w.is_alive(hwnd):
            return False, "window is gone"
        hwnd = w.top_level(hwnd)
        possible, why = self.can_exclude(hwnd)
        if not possible:
            return False, why
        ok, err = w.set_display_affinity(hwnd, w.WDA_EXCLUDEFROMCAPTURE)
        if not ok:
            return False, f"SetWindowDisplayAffinity failed (win32 error {err})"
        if w.get_display_affinity(hwnd) != w.WDA_EXCLUDEFROMCAPTURE:
            return False, "Windows accepted the call but did not apply it"
        return True, "hidden from screen capture"

    def allow_capture(self, hwnd: int) -> tuple[bool, str]:
        ok, err = w.set_display_affinity(hwnd, w.WDA_NONE)
        if not ok:
            return False, f"failed to clear affinity (win32 error {err})"
        return True, "visible to screen capture"

    # -- translucency (cosmetic) --------------------------------------------

    def dim(self, hwnd: int, rule_id: str | None = None) -> tuple[bool, str]:
        if not w.is_alive(hwnd):
            return False, "window is gone"
        if hwnd not in self._dim_restore:
            self._dim_restore[hwnd] = w.get_exstyle(hwnd)
        if not w.set_alpha(hwnd, self.dim_alpha):
            return False, "could not set window translucency"
        w.set_click_through(hwnd, not self._dimmed_interactive)
        self._dimmed[hwnd] = rule_id
        return True, (
            "dimmed and click-through - hold Ctrl to use it. "
            "Still visible in a screen share: dim is not privacy."
        )

    def set_dim_alpha(self, alpha: int) -> int:
        """How see-through dimmed windows are. Applies live to every dimmed window."""
        self.dim_alpha = max(MIN_DIM_ALPHA, min(255, int(alpha)))
        for hwnd in list(self._dimmed):
            if w.is_alive(hwnd):
                w.set_alpha(hwnd, self.dim_alpha)
        return self.dim_alpha

    def set_pinned(self, hwnd: int, pinned: bool) -> tuple[bool, str]:
        """Raise a single window above everything else, or put it back.

        Deliberately independent of dimming: dimming never changes pinning, so a
        window keeps whatever the user chose for it.
        """
        if not w.is_alive(hwnd):
            return False, "window is gone"
        if not w.set_always_on_top(hwnd, pinned):
            return False, "Windows refused to change the pinning"
        if pinned:
            self._pinned.add(hwnd)
        else:
            self._pinned.discard(hwnd)
        return True, "pinned on top" if pinned else "back in the normal stack"

    def undim(self, hwnd: int) -> tuple[bool, str]:
        self._dimmed.pop(hwnd, None)
        original = self._dim_restore.pop(hwnd, None)
        if not w.is_alive(hwnd):
            return False, "window is gone"
        if original is None:
            w.clear_alpha(hwnd)
        else:
            w.restore_exstyle(hwnd, original)
        return True, "opacity and mouse behaviour restored"

    def set_dimmed_interactive(self, interactive: bool) -> None:
        """While Ctrl is held, dimmed windows take the mouse again."""
        if interactive == self._dimmed_interactive:
            return
        self._dimmed_interactive = interactive
        for hwnd in list(self._dimmed):
            if w.is_alive(hwnd):
                w.set_click_through(hwnd, not interactive)

    # -- hiding (removes the window from the screen) -------------------------

    def hide(self, hwnd: int, rule_id: str | None = None) -> tuple[bool, str]:
        if not w.is_alive(hwnd):
            return False, "window is gone"
        if not w.hide_window(hwnd):
            return False, "could not hide window"
        self._hidden[hwnd] = rule_id
        self._hidden_meta[hwnd] = {
            "title": w.window_title(hwnd),
            "exe": w.process_name(w.window_pid(hwnd)),
        }
        return True, "hidden (not on screen, so not in the share either)"

    def show(self, hwnd: int) -> tuple[bool, str]:
        self._hidden.pop(hwnd, None)
        self._hidden_meta.pop(hwnd, None)
        if not w.is_alive(hwnd):
            return False, "window is gone"
        w.show_window(hwnd, restore=True)
        return True, "shown"

    def show_all(self) -> int:
        count = 0
        for hwnd in list(self._hidden):
            ok, _ = self.show(hwnd)
            if ok:
                count += 1
        self._hidden.clear()
        self._hidden_meta.clear()
        return count

    # -- internals ----------------------------------------------------------

    def _prune(self) -> None:
        for hwnd in list(self._dimmed):
            if not w.is_alive(hwnd):
                del self._dimmed[hwnd]
        for hwnd in list(self._dim_restore):
            if hwnd not in self._dimmed:
                del self._dim_restore[hwnd]
        self._pinned = {hwnd for hwnd in self._pinned if w.is_alive(hwnd)}
        for hwnd in list(self._hidden):
            if not w.is_alive(hwnd):
                del self._hidden[hwnd]
        for hwnd in list(self._hidden_meta):
            if hwnd not in self._hidden:
                del self._hidden_meta[hwnd]


protector = Protector()
