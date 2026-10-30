"""
Vaultix entry point.

Hosts the intro animation, the auth screen and the vault screen in one
maximized window and handles locking (manual and after inactivity).
"""

import sys

from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QStackedWidget, QDialog, QPushButton, QCheckBox,
)

from app import db
from app.branding import APP_NAME
from ui.auth_window import AuthWindow
from ui.main_window import MainWindow
from ui.security import InactivityGuard, shared_clipboard_guard
from ui.splash import SplashScreen
from ui.styles import APP_STYLE
from ui.widgets import app_icon, fade_in, theme_title_bar

_ACTIVITY_EVENTS = {QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.KeyPress, QEvent.Wheel}


class AppWindow(QWidget):
    def __init__(self, show_intro: bool = True):
        super().__init__()
        self.setObjectName("AppRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1000, 650)
        self.resize(1280, 800)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.auth_window = AuthWindow()
        self.auth_window.authenticated.connect(self._on_authenticated)
        self.stack.addWidget(self.auth_window)

        self.splash = None
        if show_intro:
            self.splash = SplashScreen()
            self.splash.finished.connect(self._end_intro)
            self.stack.addWidget(self.splash)
            self.stack.setCurrentWidget(self.splash)

        self.main_window = None
        self.inactivity_guard = InactivityGuard(timeout_minutes=5, parent=self)
        self.inactivity_guard.locked.connect(self._lock)

    def start_intro(self):
        if self.splash is not None:
            self.splash.start()

    def _end_intro(self):
        self.stack.setCurrentWidget(self.auth_window)
        self.stack.removeWidget(self.splash)
        self.splash.deleteLater()
        self.splash = None
        self.auth_window.focus_login()
        fade_in(self.auth_window, 420)

    @property
    def unlocked(self) -> bool:
        return self.main_window is not None and self.main_window.session is not None

    def _on_authenticated(self, session):
        if self.main_window is not None:
            self.stack.removeWidget(self.main_window)
            self.main_window.deleteLater()

        self.main_window = MainWindow(session)
        self.main_window.locked.connect(self._lock)
        self.main_window.auto_lock_changed.connect(self.inactivity_guard.set_timeout_minutes)
        self.stack.addWidget(self.main_window)
        self.stack.setCurrentWidget(self.main_window)
        fade_in(self.main_window, 260)

        user = db.get_user_by_id(session.user_id)
        self.inactivity_guard.set_timeout_minutes(user["auto_lock_minutes"] if user else 5)
        self.inactivity_guard.start()
        self.setWindowTitle(f"{APP_NAME} - {session.username}")

    def _lock(self):
        if not self.unlocked:
            return
        self.inactivity_guard.stop()

        # Unwind any menus/dialogs (each runs a nested event loop) before wiping data.
        while QApplication.activePopupWidget() is not None:
            QApplication.activePopupWidget().close()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.done(QDialog.Rejected)

        self.main_window.wipe()
        shared_clipboard_guard().clear_now()
        self.auth_window.refresh_usernames()
        self.stack.setCurrentWidget(self.auth_window)
        self.auth_window.focus_login()
        fade_in(self.auth_window, 260)
        self.setWindowTitle(f"{APP_NAME} - Locked")

    def note_activity(self):
        if self.unlocked:
            self.inactivity_guard.reset()


class AppEventFilter(QObject):
    """App-wide filter: feeds the inactivity timer and gives clickable widgets a hand cursor."""

    def __init__(self, window: AppWindow):
        super().__init__(window)
        self._window = window

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype in _ACTIVITY_EVENTS:
            self._window.note_activity()
        elif etype == QEvent.Polish and isinstance(obj, (QPushButton, QCheckBox)):
            obj.setCursor(Qt.PointingHandCursor)
        elif etype == QEvent.Show and isinstance(obj, QWidget) and obj.isWindow() \
                and obj.windowType() in (Qt.Window, Qt.Dialog):
            theme_title_bar(obj)
        return False


def main():
    if sys.platform == "win32":
        import ctypes
        # Own taskbar identity, so Windows shows our icon instead of python.exe's.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)

    db.init_db()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(APP_STYLE)

    window = AppWindow()
    event_filter = AppEventFilter(window)
    app.installEventFilter(event_filter)
    app.aboutToQuit.connect(shared_clipboard_guard().clear_now)
    window.showMaximized()
    window.start_intro()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
