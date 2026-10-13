"""Protected windows: Chromium (WebView2) windows owned by this process.

These are the only windows we can genuinely exclude from screen capture, because
Windows requires the caller to own the window it is protecting. Creating the
window ourselves is what makes the real feature possible.

Each one gets a navigation bar injected on every page load, so it behaves like a
small private browser rather than a bare content pane.
"""

import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import webview

from . import protect, tracker, win32api as w
from . import DASHBOARD_TITLE

ASSETS = Path(__file__).parent / "assets"
START_URL = "https://www.google.com"

CLAIM_TIMEOUT = 12.0
CLAIM_POLL = 0.15


def _label_for(url: str) -> str:
    host = urlparse(url).netloc or urlparse(url).path or url
    host = host.removeprefix("www.")
    return host[:48] or "Protected"


def _normalise(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url and not url.startswith("about:"):
        url = "https://" + url
    return url


def _read_toolbar() -> str:
    try:
        return (ASSETS / "toolbar.js").read_text(encoding="utf-8")
    except OSError:
        return ""


class _PageApi:
    """Bridge exposed to the page inside a protected window.

    Underscore-prefixed attributes only: pywebview walks public attributes of a
    js_api object to build the bridge, and anything reachable from here would be
    walked too.
    """

    def __init__(self, manager: "ProtectedWindows", tab_id: str) -> None:
        self._manager = manager
        self._tab_id = tab_id

    def new_window(self, url: str = "") -> bool:
        self._manager.new("", url)
        return True

    def close_window(self, _url: str = "") -> bool:
        self._manager.close(self._tab_id)
        return True


class ProtectedWindows:
    def __init__(self, store=None) -> None:
        self._store = store
        self._items: dict[str, dict] = {}
        self._claimed: set[int] = set()
        self._lock = threading.Lock()
        self._toolbar = _read_toolbar()

    # -- public API ---------------------------------------------------------

    def new(self, label: str = "", url: str = "") -> dict:
        """Create a protected window, remembering it for the next launch."""
        url = _normalise(url) or START_URL
        label = (label or "").strip() or _label_for(url)

        if self._store is not None:
            tab = self._store.add_tab(label, url)
        else:
            tab = {"id": uuid.uuid4().hex[:12], "label": label, "url": url}
        self.open(tab["id"], label, url)
        return tab

    def open(self, tab_id: str, label: str, url: str) -> dict:
        before = {win.hwnd for win in tracker.list_own_windows()}
        window = webview.create_window(
            label,
            url,
            width=1024,
            height=768,
            min_size=(520, 380),
            js_api=_PageApi(self, tab_id),
        )
        record = {
            "id": tab_id,
            "label": label,
            "url": url,
            "hwnd": None,
            "status": "opening",
            "window": window,
        }
        with self._lock:
            self._items[tab_id] = record

        window.events.closed += lambda: self._forget(tab_id)
        window.events.loaded += lambda: self._on_loaded(tab_id, window)

        threading.Thread(
            target=self._claim,
            args=(tab_id, window, label, before),
            name=f"cbs-claim-{tab_id}",
            daemon=True,
        ).start()
        return self._public(record)

    def close(self, tab_id: str) -> bool:
        with self._lock:
            record = self._items.get(tab_id)
        if not record:
            return False
        self._remember_url(tab_id, record)
        try:
            record["window"].destroy()
        except Exception:
            pass
        self._forget(tab_id)
        if self._store is not None:
            self._store.remove_tab(tab_id)
        return True

    def close_all(self) -> None:
        for tab_id in list(self._items):
            self.close(tab_id)

    def list(self) -> list[dict]:
        with self._lock:
            return [self._public(r) for r in self._items.values()]

    def focus(self, tab_id: str) -> bool:
        with self._lock:
            record = self._items.get(tab_id)
        if not record or not record["hwnd"]:
            return False
        w.user32.ShowWindow(record["hwnd"], w.SW_RESTORE)
        w.user32.SetForegroundWindow(record["hwnd"])
        return True

    # -- internals ----------------------------------------------------------

    def _on_loaded(self, tab_id: str, window) -> None:
        """Re-inject the navigation bar; loaded fires on every navigation."""
        if self._toolbar:
            try:
                window.evaluate_js(self._toolbar)
            except Exception:
                pass
        with self._lock:
            record = self._items.get(tab_id)
        if record is not None:
            self._remember_url(tab_id, record)

    def _remember_url(self, tab_id: str, record: dict) -> None:
        try:
            current = record["window"].get_current_url()
        except Exception:
            return
        if not current or current == record.get("url"):
            return
        record["url"] = current
        if self._store is None:
            return
        for tab in self._store.protected_tabs:
            if tab["id"] == tab_id:
                tab["url"] = current
                self._store.save()
                break

    def _claim(self, tab_id: str, window, label: str, before: set[int]) -> None:
        """Find the handle of the window we just created, then exclude it."""
        deadline = time.time() + CLAIM_TIMEOUT
        hwnd = None

        # Wait for the backend to hand us the real handle. This is the only
        # unambiguous answer, so the guesswork below is deliberately kept until
        # after this has had its chance.
        while time.time() < deadline:
            if tab_id not in self._items:
                return
            hwnd = self._native_hwnd(window)
            if hwnd:
                break
            time.sleep(CLAIM_POLL)

        if hwnd is None:
            hwnd = self._fallback_hwnd(label, before)

        with self._lock:
            record = self._items.get(tab_id)
            if record is None:
                return
            record["hwnd"] = hwnd
            if hwnd is None:
                record["status"] = "unresolved: could not find the window handle"
                return

        ok, message = protect.protector.exclude_from_capture(hwnd)
        with self._lock:
            record = self._items.get(tab_id)
            if record is not None:
                record["status"] = ("protected: " + message) if ok else ("FAILED: " + message)

    def _native_hwnd(self, window) -> int | None:
        """The top-level handle the backend reports for this window, if any."""
        native = getattr(window, "native", None)
        handle = getattr(native, "Handle", None) if native is not None else None
        if handle is None:
            return None
        try:
            hwnd = w.top_level(int(handle.ToInt64()))
        except Exception:
            return None
        if not hwnd:
            return None
        with self._lock:
            self._claimed.add(hwnd)
        return hwnd

    def _fallback_hwnd(self, label: str, before: set[int]) -> int | None:
        """Last resort if the backend never gave us a handle.

        Only reached after CLAIM_TIMEOUT, and it never touches the dashboard -
        a before/after diff of our own windows can otherwise hand back the
        dashboard and silently protect the wrong window.
        """
        own = [win for win in tracker.list_own_windows() if win.title != DASHBOARD_TITLE]

        for win in own:
            if win.title == label and win.hwnd not in self._claimed:
                with self._lock:
                    self._claimed.add(win.hwnd)
                return win.hwnd

        for win in own:
            if win.hwnd in before or win.hwnd in self._claimed:
                continue
            with self._lock:
                self._claimed.add(win.hwnd)
            return win.hwnd
        return None

    def _forget(self, tab_id: str) -> None:
        with self._lock:
            record = self._items.pop(tab_id, None)
            if record and record.get("hwnd"):
                self._claimed.discard(record["hwnd"])

    @staticmethod
    def _public(record: dict) -> dict:
        return {
            "id": record["id"],
            "label": record["label"],
            "url": record["url"],
            "hwnd": record["hwnd"],
            "status": record["status"],
        }


def protect_dashboard(window) -> tuple[bool, str]:
    """Exclude the app's own dashboard from capture."""
    for win in tracker.list_own_windows():
        if win.title == window.title:
            return protect.protector.exclude_from_capture(win.hwnd)

    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None) if native is not None else None
    if handle is not None:
        try:
            return protect.protector.exclude_from_capture(handle.ToInt64())
        except Exception as exc:
            return False, f"could not read the dashboard handle: {exc}"
    return False, "could not locate the dashboard window"
