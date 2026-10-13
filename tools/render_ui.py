"""Render the dashboard to a PNG without disturbing the desktop.

The real dashboard cannot be screenshotted: it excludes itself from capture by
default, and WebView2 does not render into PrintWindow. So load the same HTML in
headless Edge with a stubbed pywebview bridge and lay the whole page out at once.

    .venv\\Scripts\\python.exe tools\\render_ui.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "cbs" / "assets"
OUT = ROOT / "shot-ui.png"

STUB = """
<script>
window.pywebview = { api: (function () {
  const state = {
    windows: [
      { hwnd: 1001, title: "AWS Skill Builder - Google Chrome", exe: "chrome.exe", pid: 11, cls: "", ours: false, monitor: "screen 1",
        state: { dimmed: false, hidden: false, capture_excluded: false, visible: true } },
      { hwnd: 1002, title: "Slack - #team-standup", exe: "slack.exe", pid: 22, cls: "", ours: false, monitor: "screen 2",
        state: { dimmed: false, hidden: false, capture_excluded: false, visible: true } },
      { hwnd: 1003, title: "Design Feedback - Figma", exe: "chrome.exe", pid: 11, cls: "", ours: false, monitor: "screen 2",
        state: { dimmed: true, hidden: false, capture_excluded: false, visible: true, pinned: true } },
      { hwnd: 1004, title: "cannot-be-seen", exe: "pythonw.exe", pid: 33, cls: "", ours: true, monitor: "screen 1",
        state: { dimmed: false, hidden: false, capture_excluded: true, visible: true } }
    ],
    protected: [
      { id: "t1", label: "mail.google.com", url: "https://mail.google.com",
        hwnd: 656, status: "protected: hidden from screen capture" }
    ],
    rules: [
      { id: "r1", enabled: true, exe: "slack.exe", title: "", mode: "hide", alpha: 140 },
      { id: "r2", enabled: false, exe: "chrome.exe", title: "Gmail", mode: "dim", alpha: 140 }
    ],
    hidden: [ { hwnd: 1005, rule_id: "r1", title: "Slack - #team-standup", exe: "slack.exe" } ],
    dashboard_protected: false,
    dim_transparency: 45,
    monitors: ["screen 1 (1920\\u00d71080)", "screen 2 (2048\\u00d71152)"]
  };
  const ok = () => Promise.resolve({ ok: true, message: "" });
  return {
    snapshot: () => Promise.resolve(state),
    dim: ok, undim: ok, hide: ok, show_window: ok, exclude_own: ok, show_all: ok,
    move_to_other_monitor: ok, set_dim_transparency: ok, set_pinned: ok,
    always_app: ok, always_window: ok, toggle_rule: ok,
    set_rule_mode: ok, remove_rule: ok, new_protected: ok, close_protected: ok,
    focus_protected: ok, toggle_dashboard_protection: ok, open_verify: ok
  };
})() };
</script>
"""

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str | None:
    for path in BROWSERS:
        if Path(path).exists():
            return path
    return shutil.which("msedge") or shutil.which("chrome")


def main() -> int:
    browser = find_browser()
    if not browser:
        print("no Edge or Chrome found")
        return 1

    html = (ASSETS / "index.html").read_text(encoding="utf-8")
    marker = "<script>\nconst $ ="
    if marker not in html:
        print("could not find the insertion point in index.html")
        return 1

    staged = ROOT / "_render.html"
    staged.write_text(html.replace(marker, STUB + marker, 1), encoding="utf-8")
    OUT.unlink(missing_ok=True)

    # A private profile dir keeps this from attaching to an already-running
    # Edge, which makes the headless run hang.
    import tempfile

    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             f"--user-data-dir={profile}",
             "--force-device-scale-factor=1", "--virtual-time-budget=2500",
             "--window-size=1300,1150", f"--screenshot={OUT}", staged.as_uri()],
            check=False, timeout=90,
        )
    staged.unlink(missing_ok=True)

    if not OUT.exists():
        print("screenshot was not produced")
        return 1
    print(f"saved {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
