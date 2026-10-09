"""Login / Register / Account-recovery window."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QComboBox, QMessageBox, QFormLayout
)

from app import db, auth
from app.auth import Session, AuthError, AccountLockedError, TwoFactorRequiredError
from ui.dialogs import RecoveryKeyDialog, TwoFactorPromptDialog


class AuthWindow(QWidget):
    authenticated = Signal(object)  # emits Session

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SecureVaultPM")
        self.setMinimumSize(420, 420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        title = QLabel("SecureVaultPM")
        title.setObjectName("TitleLabel")
        subtitle = QLabel("Your passwords, encrypted end-to-end.")
        subtitle.setObjectName("SubtitleLabel")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._build_login_tab(), "Log In")
        tabs.addTab(self._build_register_tab(), "Create Account")
        tabs.addTab(self._build_recovery_tab(), "Forgot Password?")
        layout.addWidget(tabs)
        self._tabs = tabs

    # ---------- Login ----------

    def _build_login_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self.login_username = QComboBox()
        self.login_username.setEditable(True)
        self.login_username.addItems(db.list_usernames())

        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.returnPressed.connect(self._do_login)

        btn = QPushButton("Unlock Vault")
        btn.clicked.connect(self._do_login)

        form.addRow("Username", self.login_username)
        form.addRow("Master Password", self.login_password)
        form.addRow(btn)
        return w

    def _do_login(self):
        username = self.login_username.currentText().strip()
        password = self.login_password.text()
        if not username or not password:
            QMessageBox.warning(self, "Missing info", "Enter username and password.")
            return

        try:
            session = auth.login(username, password)
        except TwoFactorRequiredError:
            code = TwoFactorPromptDialog.get_code(self)
            if code is None:
                return
            try:
                session = auth.login(username, password, totp_code=code)
            except AccountLockedError as e:
                QMessageBox.critical(self, "Account Locked", str(e))
                return
            except AuthError as e:
                QMessageBox.warning(self, "Login Failed", str(e))
                return
        except AccountLockedError as e:
            QMessageBox.critical(self, "Account Locked", str(e))
            return
        except AuthError as e:
            QMessageBox.warning(self, "Login Failed", str(e))
            return

        self.login_password.clear()
        self.authenticated.emit(session)

    # ---------- Register ----------

    def _build_register_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self.reg_username = QLineEdit()
        self.reg_password = QLineEdit()
        self.reg_password.setEchoMode(QLineEdit.Password)
        self.reg_confirm = QLineEdit()
        self.reg_confirm.setEchoMode(QLineEdit.Password)

        btn = QPushButton("Create Account")
        btn.clicked.connect(self._do_register)

        form.addRow("Username", self.reg_username)
        form.addRow("Master Password", self.reg_password)
        form.addRow("Confirm Password", self.reg_confirm)
        form.addRow(QLabel("Minimum 8 characters. This password cannot be\nrecovered without your backup recovery key."))
        form.addRow(btn)
        return w

    def _do_register(self):
        username = self.reg_username.text().strip()
        password = self.reg_password.text()
        confirm = self.reg_confirm.text()

        if password != confirm:
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return

        try:
            session, recovery_key = auth.register_user(username, password)
        except AuthError as e:
            QMessageBox.warning(self, "Registration Failed", str(e))
            return

        self.reg_username.clear()
        self.reg_password.clear()
        self.reg_confirm.clear()

        RecoveryKeyDialog(recovery_key, session.username, self).exec()
        self.authenticated.emit(session)

    # ---------- Recovery ----------

    def _build_recovery_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)

        self.rec_username = QLineEdit()
        self.rec_key = QLineEdit()
        self.rec_key.setPlaceholderText("XXXX-XXXX-XXXX-...")
        self.rec_new_password = QLineEdit()
        self.rec_new_password.setEchoMode(QLineEdit.Password)
        self.rec_confirm_password = QLineEdit()
        self.rec_confirm_password.setEchoMode(QLineEdit.Password)

        btn = QPushButton("Reset Master Password")
        btn.clicked.connect(self._do_recover)

        form.addRow("Username", self.rec_username)
        form.addRow("Recovery Key", self.rec_key)
        form.addRow("New Master Password", self.rec_new_password)
        form.addRow("Confirm New Password", self.rec_confirm_password)
        form.addRow(btn)
        return w

    def _do_recover(self):
        if self.rec_new_password.text() != self.rec_confirm_password.text():
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        try:
            session = auth.recover_account(
                self.rec_username.text(), self.rec_key.text(), self.rec_new_password.text()
            )
        except AuthError as e:
            QMessageBox.warning(self, "Recovery Failed", str(e))
            return

        QMessageBox.information(self, "Success", "Master password reset. You are now logged in.")
        self.rec_key.clear()
        self.rec_new_password.clear()
        self.rec_confirm_password.clear()
        self.authenticated.emit(session)

    def refresh_usernames(self):
        self.login_username.clear()
        self.login_username.addItems(db.list_usernames())
