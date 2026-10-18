"""
Runtime security hardening:
- InactivityGuard: locks the vault after N minutes without user input.
- ClipboardGuard: wipes the clipboard a short time after a password is
  copied, so it doesn't linger for other apps/clipboard managers to read.
"""

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication


class InactivityGuard(QObject):
    locked = Signal()

    def __init__(self, timeout_minutes: int = 5, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.locked.emit)
        self.set_timeout_minutes(timeout_minutes)

    def set_timeout_minutes(self, minutes: int):
        self._timeout_ms = max(minutes, 1) * 60 * 1000
        if self._timer.isActive():
            self._timer.start(self._timeout_ms)

    def start(self):
        self._timer.start(self._timeout_ms)

    def stop(self):
        self._timer.stop()

    def reset(self):
        if self._timer.isActive() or self._timer.remainingTime() >= 0:
            self._timer.start(self._timeout_ms)


class ClipboardGuard(QObject):
    """Clears the clipboard after `seconds`, but only if it still contains
    the exact text we copied (so we don't wipe something the user copied
    from elsewhere afterwards)."""

    def __init__(self, seconds: int = 25, parent=None):
        super().__init__(parent)
        self._seconds = seconds
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._clear)
        self._last_copied = None

    def copy(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self._last_copied = text
        self._timer.start(self._seconds * 1000)

    def _clear(self):
        clipboard = QApplication.clipboard()
        if clipboard.text() == self._last_copied:
            clipboard.clear()
        self._last_copied = None

    def clear_now(self):
        if self._last_copied is not None:
            self._timer.stop()
            self._clear()


_shared_clipboard_guard = None


def shared_clipboard_guard() -> ClipboardGuard:
    global _shared_clipboard_guard
    if _shared_clipboard_guard is None:
        _shared_clipboard_guard = ClipboardGuard(seconds=25, parent=QApplication.instance())
    return _shared_clipboard_guard
