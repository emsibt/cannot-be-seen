"""Checks that the protected-window browser profile persists between launches.

Runs itself twice as separate processes against one profile: the first stores a
cookie and a localStorage entry on a real origin, the second reads them back. If
pywebview falls back to its default private_mode the second process sees nothing,
which is exactly what forces a fresh login every time.

    .venv\\Scripts\\python.exe tests\\check_profile_persistence.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

URL = "https://example.com"
MARKER = "cbs-persist-7f3a"

WRITE_JS = """
(function () {
  try { localStorage.setItem('cbs-test', %s); } catch (e) {}
  document.cookie = 'cbs_test=' + %s + '; path=/; max-age=3600';
  return 'written';
})()
""" % (json.dumps(MARKER), json.dumps(MARKER))

READ_JS = """
JSON.stringify({
  ls: (function () { try { return localStorage.getItem('cbs-test'); } catch (e) { return null; } })(),
  cookie: document.cookie
})
"""


def phase_main(phase: str, profile: Path) -> int:
    import webview

    outcome: dict = {"value": None}

    def worker() -> None:
        deadline = time.time() + 40
        while time.time() < deadline and not webview.windows:
            time.sleep(0.2)
        if not webview.windows:
            return
        window = webview.windows[0]

        while time.time() < deadline:
            try:
                if window.evaluate_js("document.readyState") in ("interactive", "complete"):
                    break
            except Exception:
                pass
            time.sleep(0.3)
        time.sleep(0.5)

        try:
            outcome["value"] = window.evaluate_js(WRITE_JS if phase == "write" else READ_JS)
        except Exception as exc:
            outcome["value"] = f"error: {exc}"
        try:
            window.destroy()
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True).start()
    webview.create_window("cbs-profile-test", URL)
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(profile))

    print(json.dumps({"phase": phase, "value": outcome["value"]}))
    return 0


def run_phase(phase: str, profile: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), phase, str(profile)],
        capture_output=True, text=True, timeout=180,
    )
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"phase": phase, "value": None, "stderr": completed.stderr[-400:]}


def main() -> int:
    if len(sys.argv) > 2:
        return phase_main(sys.argv[1], Path(sys.argv[2]))

    profile = Path(tempfile.gettempdir()) / "cbs-profile-test"
    shutil.rmtree(profile, ignore_errors=True)

    print(f"profile: {profile}\n")
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"  [{'ok  ' if condition else 'FAIL'}] {label}{f' - {detail}' if detail else ''}")
        if not condition:
            failures.append(label)

    written = run_phase("write", profile)
    check("first launch stored a cookie", written.get("value") == "written",
          str(written.get("value"))[:120])

    read = run_phase("read", profile)
    raw = read.get("value")
    if not isinstance(raw, str):
        check("second launch read the profile back", False, str(raw)[:200])
    else:
        data = json.loads(raw)
        check("localStorage survived the restart", data.get("ls") == MARKER, str(data.get("ls")))
        check("cookie survived the restart", f"cbs_test={MARKER}" in (data.get("cookie") or ""),
              str(data.get("cookie"))[:80])

    check("profile folder exists on disk", profile.exists(), str(profile))
    shutil.rmtree(profile, ignore_errors=True)

    print()
    if failures:
        print(f"FAILED: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
