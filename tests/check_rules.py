"""Checks the dim/hide rule engine against a window owned by another process.

    .venv\\Scripts\\python.exe tests\\check_rules.py
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cbs import protect, rules, tracker, win32api as w

# Unique per run, so a window left behind by a killed run cannot be mistaken for
# this one's target.
TITLE = f"CBS-TEST-TARGET-{os.getpid()}"

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {label}{f' - {detail}' if detail else ''}")
    if not condition:
        failures.append(label)


def find_target(hwnd_hint: int | None = None) -> int | None:
    for win in tracker.list_windows():
        if win.title == TITLE:
            return win.hwnd
    return hwnd_hint


def main() -> int:
    target = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "target_window.py"), TITLE]
    )
    try:
        return run_checks()
    finally:
        target.terminate()


def run_checks() -> int:
    hwnd = None
    for _ in range(60):
        time.sleep(0.2)
        hwnd = find_target()
        if hwnd:
            break
    if not hwnd:
        print("FAIL: target window never appeared")
        return 1

    print(f"target hwnd = 0x{hwnd:X}\n")

    with tempfile.TemporaryDirectory() as tmp:
        store = rules.Store(path=Path(tmp) / "config.json")
        watcher = rules.Watcher(store, protect.protector)

        # --- dim ----------------------------------------------------------
        print("dim rule")
        store.add_rule(exe="python.exe", title=TITLE, mode="dim")
        watcher.tick()
        state = protect.protector.state_of(hwnd)
        check("window is dimmed", state["dimmed"])
        check("window is still visible", state["visible"])
        check("WS_EX_LAYERED applied", bool(w.get_exstyle(hwnd) & w.WS_EX_LAYERED))

        # --- hide ---------------------------------------------------------
        print("hide rule")
        store.update_rule(store.rules[0]["id"], mode="hide")
        watcher.tick()
        check("window is hidden", not w.user32.IsWindowVisible(hwnd))
        check("window is tracked as hidden", any(h["hwnd"] == hwnd for h in protect.protector.hidden))

        # hiding removes it from the on-screen list, which is what makes it
        # absent from a screen share
        check("hidden window drops off the on-screen list", find_target(hwnd) is None or
              not w.user32.IsWindowVisible(hwnd))

        # --- a window re-shown behind our back gets re-hidden --------------
        print("re-hide after the app re-shows itself")
        w.show_window(hwnd)
        time.sleep(0.1)
        watcher.tick()
        check("re-hidden on the next tick", not w.user32.IsWindowVisible(hwnd))

        # --- show all -----------------------------------------------------
        print("restore")
        protect.protector.show_all()
        check("window is visible again", bool(w.user32.IsWindowVisible(hwnd)))

        # --- a dim the rule applied is released when the rule goes off ------
        print("rule-driven dim is released")
        rule_id = store.rules[0]["id"]
        store.update_rule(rule_id, mode="dim")
        watcher.tick()
        check("rule dimmed the window", protect.protector.state_of(hwnd)["dimmed"])
        store.update_rule(rule_id, enabled=False)
        watcher.tick()
        check("released once the rule is off",
              not protect.protector.state_of(hwnd)["dimmed"])
        check("WS_EX_LAYERED removed", not w.get_exstyle(hwnd) & w.WS_EX_LAYERED)

        # --- a dim the user set by hand must survive the watcher ------------
        # regression: the loop used to undo any dim with no matching rule,
        # so clicking Dim in the dashboard appeared to switch itself off
        print("manual dim survives the watcher")
        protect.protector.dim(hwnd)
        watcher.tick()
        watcher.tick()
        check("still dimmed after two ticks",
              protect.protector.state_of(hwnd)["dimmed"])
        protect.protector.undim(hwnd)
        check("cleared on request", not protect.protector.state_of(hwnd)["dimmed"])

        # --- capture exclusion is refused for a foreign window -------------
        print("capture exclusion on a foreign window")
        ok, message = protect.protector.exclude_from_capture(hwnd)
        check("refused, as Windows requires ownership", not ok, message)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
