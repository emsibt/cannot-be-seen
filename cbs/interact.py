"""Hold Ctrl to interact with a dimmed window.

Windows has no "click-through unless a modifier is held" flag, so we poll the key
state and flip ``WS_EX_TRANSPARENT`` on the dimmed windows ourselves. The poll is
cheap - ``GetAsyncKeyState`` is a local read - and the protector ignores calls
that would not change anything.
"""

import threading

from . import win32api as w
from .protect import Protector

POLL_SECONDS = 0.03


class CtrlGate:
    def __init__(self, protection: Protector) -> None:
        self._protection = protection
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cbs-ctrl-gate", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._protection.set_dimmed_interactive(False)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._protection.set_dimmed_interactive(w.ctrl_is_down())
            except Exception:
                pass
            self._stop.wait(POLL_SECONDS)
