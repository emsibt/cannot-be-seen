"""Application wiring: dashboard UI, tray icon, and the automation loop."""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

import webview

from . import browser, interact, protect, rules, screens, tracker, tray
from . import DASHBOARD_TITLE

ASSETS = Path(__file__).parent / "assets"

# WebView2 profile for the protected windows. Kept out of the temp folder and
# reused every launch so cookies and sessions survive - that is what makes
# "stay logged in" work. pywebview defaults to private_mode, which throws the
# profile away on exit and would force a fresh login every time.
PROFILE_DIR = rules.CONFIG_DIR / "webview"


def log(message: str) -> None:
    print(f"[cbs] {message}", flush=True)


class Api:
    """Methods exposed to the dashboard JavaScript as ``pywebview.api``.

    Every attribute here is underscore-prefixed on purpose: pywebview walks the
    public attributes of the js_api object to build the JS bridge, and an
    unhidden reference to a webview Window sends it into infinite recursion.
    """

    def __init__(self, store: rules.Store, watcher: rules.Watcher, protected: browser.ProtectedWindows):
        self._store = store
        self._watcher = watcher
        self._protected = protected
        self._dashboard = None
        self._dashboard_protected = False

    # -- read ---------------------------------------------------------------

    def snapshot(self) -> dict:
        monitors = screens.list_monitors()
        by_handle = {m["handle"]: m["name"] for m in monitors}

        windows = []
        for win in tracker.list_windows():
            entry = win.to_dict()
            entry["state"] = protect.protector.state_of(win.hwnd)
            entry["monitor"] = by_handle.get(screens.monitor_of(win.hwnd), "")
            windows.append(entry)
        return {
            "windows": windows,
            "protected": self._protected.list(),
            "rules": self._store.rules,
            "hidden": protect.protector.hidden,
            "dashboard_protected": self._dashboard_protected,
            "monitors": [m["label"] for m in monitors],
            "dim_transparency": self.dim_transparency(),
        }

    def dim_transparency(self) -> int:
        """How see-through dimmed windows are, as a percentage."""
        return round((1 - protect.protector.dim_alpha / 255) * 100)

    # -- foreign-window actions --------------------------------------------

    def dim(self, hwnd: int) -> dict:
        return self._result(*protect.protector.dim(int(hwnd)))

    def undim(self, hwnd: int) -> dict:
        return self._result(*protect.protector.undim(int(hwnd)))

    def hide(self, hwnd: int) -> dict:
        return self._result(*protect.protector.hide(int(hwnd)))

    def show_window(self, hwnd: int) -> dict:
        return self._result(*protect.protector.show(int(hwnd)))

    def exclude_own(self, hwnd: int) -> dict:
        """Capture exclusion, for windows this process created."""
        return self._result(*protect.protector.exclude_from_capture(int(hwnd)))

    def move_to_other_monitor(self, hwnd: int) -> dict:
        """Park a window on a display that isn't the one it is on now.

        The only route that keeps another app's window readable and interactive
        while staying out of a share: share one monitor, keep it on the other.
        """
        return self._result(*screens.move_to_other_monitor(int(hwnd)))

    def set_dim_transparency(self, percent: int) -> dict:
        """Set how see-through dimmed windows are. Applies to them immediately."""
        percent = max(0, min(90, int(percent)))
        alpha = protect.protector.set_dim_alpha(round(255 * (1 - percent / 100)))
        self._store.dim_alpha = alpha
        self._store.save()
        return {"ok": True, "message": ""}

    def set_pinned(self, hwnd: int, pinned: bool) -> dict:
        """Pin one window above everything else, or put it back. Per window."""
        return self._result(*protect.protector.set_pinned(int(hwnd), bool(pinned)))

    def show_all(self) -> dict:
        rule_ids = {h["rule_id"] for h in protect.protector.hidden if h.get("rule_id")}
        count = protect.protector.show_all()
        for rule_id in rule_ids:
            self._store.update_rule(rule_id, enabled=False)
        message = f"restored {count} window(s)"
        if rule_ids:
            message += f"; {len(rule_ids)} rule(s) switched off so they stay visible"
        return {"ok": True, "message": message}

    # -- rules --------------------------------------------------------------

    def _find(self, hwnd: int) -> tracker.Window | None:
        for win in tracker.list_windows():
            if win.hwnd == hwnd:
                return win
        return None

    def always_app(self, hwnd: int) -> dict:
        win = self._find(int(hwnd))
        if not win:
            return {"ok": False, "message": "that window is gone"}
        self._store.add_rule(exe=win.exe, title="", mode="hide")
        return {"ok": True, "message": f"every {win.exe} window is now hidden — change the mode in Rules"}

    def always_window(self, hwnd: int) -> dict:
        win = self._find(int(hwnd))
        if not win:
            return {"ok": False, "message": "that window is gone"}
        self._store.add_rule(exe=win.exe, title=win.title, mode="hide")
        return {"ok": True, "message": "rule added (mode: hide)"}

    def toggle_rule(self, rule_id: str, enabled: bool) -> dict:
        self._store.update_rule(rule_id, enabled=bool(enabled))
        return {"ok": True, "message": ""}

    def set_rule_mode(self, rule_id: str, mode: str) -> dict:
        if mode not in rules.MODES:
            return {"ok": False, "message": f"unknown mode {mode}"}
        self._store.update_rule(rule_id, mode=mode)
        return {"ok": True, "message": ""}

    def remove_rule(self, rule_id: str) -> dict:
        self._store.remove_rule(rule_id)
        return {"ok": True, "message": "rule removed"}

    # -- protected windows --------------------------------------------------

    def new_protected(self, label: str, url: str) -> dict:
        tab = self._protected.new(label, url)
        return {"ok": True, "message": f"opening {tab['label']}"}

    def close_protected(self, tab_id: str) -> dict:
        self._protected.close(tab_id)
        return {"ok": True, "message": "closed"}

    def focus_protected(self, tab_id: str) -> dict:
        ok = self._protected.focus(tab_id)
        return {"ok": ok, "message": "" if ok else "window is not ready yet"}

    def reopen_tabs(self) -> dict:
        for tab in self._store.protected_tabs:
            self._protected.open(tab["id"], tab["label"], tab["url"])
        return {"ok": True, "message": ""}

    # -- dashboard ----------------------------------------------------------

    def dashboard_hwnd(self) -> int | None:
        for win in tracker.list_own_windows():
            if win.title == DASHBOARD_TITLE:
                return win.hwnd
        return None

    def toggle_dashboard_protection(self, enabled: bool) -> dict:
        hwnd = self.dashboard_hwnd()
        if hwnd is None:
            return {"ok": False, "message": "dashboard window not found"}
        if enabled:
            ok, message = protect.protector.exclude_from_capture(hwnd)
        else:
            ok, message = protect.protector.allow_capture(hwnd)
        self._dashboard_protected = bool(ok and enabled)
        self._store.dashboard_protected = self._dashboard_protected
        self._store.save()
        return {"ok": ok, "message": message}

    def open_verify(self) -> dict:
        webbrowser.open((ASSETS / "verify.html").as_uri())
        return {"ok": True, "message": "opened the capture test in your browser"}

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _result(ok: bool, message: str) -> dict:
        return {"ok": bool(ok), "message": message}


class Application:
    def __init__(self) -> None:
        self.store = rules.Store()
        self.watcher = rules.Watcher(self.store, protect.protector)
        self.protected = browser.ProtectedWindows(self.store)
        self.ctrl_gate = interact.CtrlGate(protect.protector)
        self.api = Api(self.store, self.watcher, self.protected)
        self.icon = None
        self._tabs_reopened = False
        protect.protector.set_dim_alpha(self.store.dim_alpha)

    def run(self) -> None:
        dashboard = webview.create_window(
            DASHBOARD_TITLE,
            (ASSETS / "index.html").as_uri(),
            width=1220,
            height=880,
            min_size=(900, 600),
            js_api=self.api,
        )
        self.api._dashboard = dashboard
        dashboard.events.loaded += self._on_dashboard_loaded

        self.watcher.start()
        self.ctrl_gate.start()
        self._start_tray()

        log(f"browser profile: {PROFILE_DIR}")
        log("starting ui loop")
        webview.start(
            gui="edgechromium",
            private_mode=False,
            storage_path=str(PROFILE_DIR),
        )
        log("ui loop ended")

    def _on_dashboard_loaded(self) -> None:
        # Saved tabs are reopened from here rather than before the ui loop, so
        # the dashboard window already exists when they are claimed.
        self._reopen_saved_tabs()

        if not self.store.dashboard_protected:
            log("dashboard protection: off by setting")
            return
        hwnd = self.api.dashboard_hwnd()
        if hwnd is None:
            log("dashboard protection: window not found")
            return
        ok, message = protect.protector.exclude_from_capture(hwnd)
        self.api._dashboard_protected = ok
        log(f"dashboard protection: ok={ok} {message}")

    def _reopen_saved_tabs(self) -> None:
        if self._tabs_reopened:
            return
        self._tabs_reopened = True
        self.api.reopen_tabs()

    # -- tray ---------------------------------------------------------------

    def _start_tray(self) -> None:
        handlers = {
            "dashboard": lambda *_: self._show_dashboard(),
            "new_window": lambda *_: self._new_protected_window(),
            "show_all": lambda *_: self.api.show_all(),
            "toggle_dashboard": lambda *_: self.api.toggle_dashboard_protection(
                not self.api._dashboard_protected
            ),
            "dashboard_protected": lambda: self.api._dashboard_protected,
            "quit": lambda *_: self._quit(),
        }
        self.icon = tray.build_icon(handlers)
        threading.Thread(target=self.icon.run, name="cbs-tray", daemon=True).start()
        log("tray started")

    def _new_protected_window(self) -> None:
        self.protected.new()

    def _show_dashboard(self) -> None:
        dashboard = self.api._dashboard
        if dashboard:
            try:
                dashboard.show()
                dashboard.restore()
            except Exception as exc:
                log(f"could not show dashboard: {exc}")

    def _quit(self) -> None:
        log("quitting")
        self.watcher.stop()
        self.ctrl_gate.stop()
        self.protected.close_all()
        if self.icon:
            self.icon.stop()
        for window in list(webview.windows):
            try:
                window.destroy()
            except Exception:
                pass


def main() -> int:
    Application().run()
    return 0
