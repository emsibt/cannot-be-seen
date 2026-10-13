"""Persisted automation rules and the background loop that enforces them."""

import json
import os
import threading
import time
import uuid
from pathlib import Path

from . import protect, tracker

CONFIG_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "cannot-be-seen"
CONFIG_PATH = CONFIG_DIR / "config.json"

POLL_SECONDS = 0.75

MODES = ("dim", "hide")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Store:
    """Rules for other apps' windows, plus the list of protected tabs."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self.rules: list[dict] = []
        self.protected_tabs: list[dict] = []
        self.dashboard_protected: bool = True
        self.dim_alpha: int = protect.DEFAULT_DIM_ALPHA
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.rules = [r for r in data.get("rules", []) if isinstance(r, dict)]
        self.protected_tabs = [t for t in data.get("protected_tabs", []) if isinstance(t, dict)]
        self.dashboard_protected = bool(data.get("dashboard_protected", True))
        try:
            self.dim_alpha = int(data.get("dim_alpha", protect.DEFAULT_DIM_ALPHA))
        except (TypeError, ValueError):
            self.dim_alpha = protect.DEFAULT_DIM_ALPHA

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {
                "rules": self.rules,
                "protected_tabs": self.protected_tabs,
                "dashboard_protected": self.dashboard_protected,
                "dim_alpha": self.dim_alpha,
            },
            indent=2,
        )
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.path)

    # -- rules --------------------------------------------------------------

    def add_rule(self, exe: str, title: str, mode: str) -> dict:
        exe = (exe or "").strip().lower()
        title = (title or "").strip()
        if not exe and not title:
            raise ValueError("a rule needs at least an app or a title to match on")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        rule = {
            "id": _new_id(),
            "enabled": True,
            "exe": exe,
            "title": title,
            "mode": mode,
        }
        self.rules.append(rule)
        self.save()
        return rule

    def update_rule(self, rule_id: str, **changes) -> dict | None:
        for rule in self.rules:
            if rule["id"] == rule_id:
                rule.update(changes)
                self.save()
                return rule
        return None

    def remove_rule(self, rule_id: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r["id"] != rule_id]
        if len(self.rules) != before:
            self.save()
            return True
        return False

    # -- protected tabs -----------------------------------------------------

    def add_tab(self, label: str, url: str) -> dict:
        tab = {"id": _new_id(), "label": label or "Protected", "url": url or "about:blank"}
        self.protected_tabs.append(tab)
        self.save()
        return tab

    def remove_tab(self, tab_id: str) -> bool:
        before = len(self.protected_tabs)
        self.protected_tabs = [t for t in self.protected_tabs if t["id"] != tab_id]
        if len(self.protected_tabs) != before:
            self.save()
            return True
        return False


def matches(rule: dict, win: tracker.Window) -> bool:
    if rule.get("exe") and rule["exe"] != win.exe:
        return False
    if rule.get("title") and rule["title"].lower() not in win.title.lower():
        return False
    return True


class Watcher:
    """Re-applies rules continuously so reopened windows stay covered.

    This is what makes 'even if I open it again' work: the loop re-evaluates
    every on-screen window instead of acting once.
    """

    def __init__(self, store: Store, protection: protect.Protector) -> None:
        self.store = store
        self.protection = protection
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cbs-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # keep the loop alive no matter what
                self.last_error = f"{type(exc).__name__}: {exc}"
            self._stop.wait(POLL_SECONDS)

    def tick(self) -> None:
        rules = [r for r in self.store.rules if r.get("enabled")]
        windows = [win for win in tracker.list_windows() if not win.ours]

        wanted_dim: dict[int, dict] = {}
        wanted_hide: dict[int, dict] = {}
        for rule in rules:
            for win in windows:
                if not matches(rule, win):
                    continue
                if rule["mode"] == "hide":
                    wanted_hide.setdefault(win.hwnd, rule)
                else:
                    wanted_dim.setdefault(win.hwnd, rule)

        # dim: apply to newly matched, but only release the ones a rule applied -
        # a dim the user set by hand has no rule and must survive the next tick
        for hwnd, rule in wanted_dim.items():
            if hwnd not in self.protection._dimmed:
                self.protection.dim(hwnd, rule["id"])
        for hwnd, rule_id in list(self.protection._dimmed.items()):
            if rule_id is not None and hwnd not in wanted_dim:
                self.protection.undim(hwnd)

        # hide: newly matched, plus anything the user managed to re-show
        for hwnd, rule in wanted_hide.items():
            if hwnd not in self.protection._hidden:
                self.protection.hide(hwnd, rule["id"])
        for hwnd in list(self.protection._hidden):
            if not protect.w.is_alive(hwnd):
                self.protection._hidden.pop(hwnd, None)
            elif protect.w.user32.IsWindowVisible(hwnd):
                self.protection.hide(hwnd, self.protection._hidden.get(hwnd))
