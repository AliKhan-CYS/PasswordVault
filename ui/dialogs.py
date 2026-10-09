"""Modal dialogs: recovery key display, 2FA prompt/setup, item editor, change password."""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QCheckBox, QMessageBox, QFormLayout, QFileDialog,
    QProgressBar, QComboBox, QSpinBox
)

from app import totp as totp_mod, vault, recovery as recovery_mod
from ui.styles import STRENGTH_COLORS


class RecoveryKeyDialog(QDialog):
    """Shown once at registration (or recovery-key rotation). Forces the
    user to acknowledge they've saved the key before closing."""

    def __init__(self, recovery_key: str, username: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Your Recovery Key")
        self.setMinimumWidth(480)
        self._recovery_key = recovery_key
        self._username = username

        layout = QVBoxLayout(self)
        warning = QLabel(
            "This recovery key is the ONLY way to reset your master password "
            "if you forget it. It will not be shown again. Store it somewhere "
            "safe and offline (e.g. a USB drive or printed note)."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        key_box = QTextEdit(recovery_key)
        key_box.setReadOnly(True)
        key_box.setFixedHeight(60)
        key_box.setStyleSheet("font-family: Consolas, monospace; font-size: 15px;")
        layout.addWidget(key_box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save to File...")
        save_btn.clicked.connect(self._save_to_file)
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setObjectName("SecondaryButton")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(copy_btn)
        layout.addLayout(btn_row)

        self.ack_checkbox = QCheckBox("I have saved this recovery key somewhere safe.")
        layout.addWidget(self.ack_checkbox)

        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.accept)
        self.ack_checkbox.toggled.connect(self.continue_btn.setEnabled)
        layout.addWidget(self.continue_btn)

        self.setModal(True)

    def _save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Recovery Token", f"{self._username}_recovery_token.json", "JSON Files (*.json)"
        )
        if path:
            recovery_mod.write_recovery_file(path, self._username, self._recovery_key)
            QMessageBox.information(self, "Saved", f"Recovery token saved to:\n{path}")

    def _copy(self):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._recovery_key)

    def closeEvent(self, event):
        if not self.ack_checkbox.isChecked():
            resp = QMessageBox.warning(
                self, "Are you sure?",
                "If you close this without saving your recovery key, you may "
                "permanently lose access to your vault if you forget your "
                "password. Close anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp == QMessageBox.No:
                event.ignore()
                return
        event.accept()


class TwoFactorPromptDialog(QDialog):
    """Prompts for a 6-digit TOTP code during login."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Two-Factor Authentication")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter the 6-digit code from your authenticator app:"))
        self.code_edit = QLineEdit()
        self.code_edit.setMaxLength(6)
        self.code_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.code_edit)
        btn = QPushButton("Verify")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    @staticmethod
    def get_code(parent=None):
        dlg = TwoFactorPromptDialog(parent)
        if dlg.exec() == QDialog.Accepted:
            return dlg.code_edit.text().strip()
        return None


class TwoFactorSetupDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Set Up Two-Factor Authentication")
        self.setMinimumWidth(360)

        self.secret = totp_mod.generate_secret()
        qr_bytes = totp_mod.make_qr_png_bytes(self.secret, session.username)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("1. Scan this QR code with Google Authenticator, Authy, etc."))

        qr_label = QLabel()
        pix = QPixmap()
        pix.loadFromData(qr_bytes)
        qr_label.setPixmap(pix.scaled(220, 220, Qt.KeepAspectRatio))
        qr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr_label)

        layout.addWidget(QLabel(f"Or enter this key manually: {self.secret}"))
        layout.addWidget(QLabel("2. Enter the 6-digit code to confirm:"))

        self.code_edit = QLineEdit()
        self.code_edit.setMaxLength(6)
        layout.addWidget(self.code_edit)

        confirm_btn = QPushButton("Enable 2FA")
        confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(confirm_btn)

    def _confirm(self):
        try:
            totp_mod.enable_2fa(self.session, self.secret, self.code_edit.text())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Code", str(e))
            return
        QMessageBox.information(self, "2FA Enabled", "Two-factor authentication is now active on your account.")
        self.accept()


class ChangePasswordDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Change Master Password")
        self.setMinimumWidth(360)

        form = QFormLayout(self)
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.Password)
        self.confirm_pw = QLineEdit()
        self.confirm_pw.setEchoMode(QLineEdit.Password)

        form.addRow("New Master Password", self.new_pw)
        form.addRow("Confirm Password", self.confirm_pw)

        btn = QPushButton("Change Password")
        btn.clicked.connect(self._submit)
        form.addRow(btn)

    def _submit(self):
        from app import auth as auth_mod
        if self.new_pw.text() != self.confirm_pw.text():
            QMessageBox.warning(self, "Mismatch", "Passwords do not match.")
            return
        try:
            auth_mod.change_master_password(self.session, self.new_pw.text())
        except auth_mod.AuthError as e:
            QMessageBox.warning(self, "Error", str(e))
            return
        QMessageBox.information(self, "Success", "Master password changed.")
        self.accept()


class PasswordGeneratorWidget(QDialog):
    """Standalone generator the user can open from the item editor or settings."""

    def __init__(self, parent=None, on_use=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Password")
        self.setMinimumWidth(400)
        self.on_use = on_use

        layout = QVBoxLayout(self)

        self.result_edit = QLineEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 14px;")
        layout.addWidget(self.result_edit)

        self.strength_bar = QProgressBar()
        self.strength_bar.setRange(0, 4)
        self.strength_bar.setTextVisible(False)
        layout.addWidget(self.strength_bar)
        self.strength_label = QLabel()
        layout.addWidget(self.strength_label)

        form = QFormLayout()
        self.length_spin = QSpinBox()
        self.length_spin.setRange(8, 64)
        self.length_spin.setValue(20)
        form.addRow("Length", self.length_spin)

        self.upper_cb = QCheckBox("Uppercase (A-Z)")
        self.upper_cb.setChecked(True)
        self.lower_cb = QCheckBox("Lowercase (a-z)")
        self.lower_cb.setChecked(True)
        self.digits_cb = QCheckBox("Digits (0-9)")
        self.digits_cb.setChecked(True)
        self.symbols_cb = QCheckBox("Symbols (!@#...)")
        self.symbols_cb.setChecked(True)
        for cb in (self.upper_cb, self.lower_cb, self.digits_cb, self.symbols_cb):
            form.addRow(cb)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        regen_btn = QPushButton("Regenerate")
        regen_btn.clicked.connect(self._generate)
        btn_row.addWidget(regen_btn)
        if self.on_use:
            use_btn = QPushButton("Use This Password")
            use_btn.clicked.connect(self._use)
            btn_row.addWidget(use_btn)
        layout.addLayout(btn_row)

        self._generate()

    def _generate(self):
        pw = vault.generate_password(
            length=self.length_spin.value(),
            use_upper=self.upper_cb.isChecked(),
            use_lower=self.lower_cb.isChecked(),
            use_digits=self.digits_cb.isChecked(),
            use_symbols=self.symbols_cb.isChecked(),
        )
        self.result_edit.setText(pw)
        info = vault.password_strength(pw)
        self.strength_bar.setValue(info["score"])
        color = STRENGTH_COLORS[info["score"]]
        self.strength_bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; }}")
        self.strength_label.setText(f"Estimated crack time: {info['crack_time_display']}")

    def _use(self):
        if self.on_use:
            self.on_use(self.result_edit.text())
        self.accept()


class ItemEditorDialog(QDialog):
    def __init__(self, parent=None, item: vault.VaultItem = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Entry" if item else "Add Entry")
        self.setMinimumWidth(420)
        self.item = item

        form = QFormLayout(self)

        self.title_edit = QLineEdit(item.title if item else "")
        self.site_edit = QLineEdit(item.website_or_app if item else "")
        self.username_edit = QLineEdit(item.username if item else "")

        pw_row = QHBoxLayout()
        self.password_edit = QLineEdit(item.password if item else "")
        self.password_edit.setEchoMode(QLineEdit.Password)
        show_btn = QPushButton("Show")
        show_btn.setObjectName("SecondaryButton")
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda checked: self.password_edit.setEchoMode(
                QLineEdit.Normal if checked else QLineEdit.Password
            )
        )
        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("SecondaryButton")
        gen_btn.clicked.connect(self._open_generator)
        pw_row.addWidget(self.password_edit)
        pw_row.addWidget(show_btn)
        pw_row.addWidget(gen_btn)

        self.notes_edit = QTextEdit(item.notes if item else "")
        self.notes_edit.setFixedHeight(80)

        form.addRow("Title", self.title_edit)
        form.addRow("Website / App", self.site_edit)
        form.addRow("Username / Email", self.username_edit)
        form.addRow("Password", pw_row)
        form.addRow("Notes", self.notes_edit)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        form.addRow(save_btn)

    def _open_generator(self):
        dlg = PasswordGeneratorWidget(self, on_use=self.password_edit.setText)
        dlg.exec()

    def get_item(self) -> vault.VaultItem:
        return vault.VaultItem(
            id=self.item.id if self.item else None,
            title=self.title_edit.text().strip(),
            website_or_app=self.site_edit.text().strip(),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            notes=self.notes_edit.toPlainText().strip(),
        )
