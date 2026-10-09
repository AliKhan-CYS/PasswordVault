"""
SecureVaultPM entry point.

Wires together the auth window and the main vault window inside a single
top-level container, and manages the inactivity auto-lock timer.
"""

import sys

from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QApplication, QWidget, QStackedLayout

from app import db
from ui.auth_window import AuthWindow
from ui.main_window import MainWindow
from ui.security import InactivityGuard
from ui.styles import APP_STYLE


class AppWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureVaultPM")
        self.resize(760, 560)

        self.stack = QStackedLayout(self)
        self.auth_window = AuthWindow()
        self.auth_window.authenticated.connect(self._on_authenticated)
        self.stack.addWidget(self.auth_window)

        self.main_window = None
        self.inactivity_guard = InactivityGuard(timeout_minutes=5)
        self.inactivity_guard.locked.connect(self._on_auto_lock)

        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (
            QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel
        ):
            self.inactivity_guard.reset()
        return super().eventFilter(obj, event)

    def _on_authenticated(self, session):
        if self.main_window is not None:
            self.stack.removeWidget(self.main_window)
            self.main_window.deleteLater()

        self.main_window = MainWindow(session)
        self.main_window.locked.connect(self._on_manual_lock)
        self.main_window.installEventFilter(self)
        self.stack.addWidget(self.main_window)
        self.stack.setCurrentWidget(self.main_window)

        user = db.get_user_by_id(session.user_id)
        minutes = user["auto_lock_minutes"] if user else 5
        self.apply_auto_lock_minutes(minutes)
        self.inactivity_guard.start()

        self.setWindowTitle(f"SecureVaultPM — {session.username}")

    def apply_auto_lock_minutes(self, minutes: int):
        self.inactivity_guard.set_timeout_minutes(minutes)

    def _lock(self):
        self.inactivity_guard.stop()
        if self.main_window is not None:
            self.main_window.session.dek = b""  # scrub key from memory
        self.auth_window.refresh_usernames()
        self.stack.setCurrentWidget(self.auth_window)
        self.setWindowTitle("SecureVaultPM — Locked")

    def _on_manual_lock(self):
        self._lock()

    def _on_auto_lock(self):
        self._lock()


def main():
    db.init_db()
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
