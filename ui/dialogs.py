"""Modal dialogs: recovery key, 2FA, re-authentication, password change, generator, item editor."""

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QPlainTextEdit, QCheckBox, QMessageBox, QFileDialog, QSlider, QSpinBox,
    QGridLayout, QFrame,
)

from app import totp as totp_mod, vault, recovery as recovery_mod, auth as auth_mod
from ui.security import shared_clipboard_guard
from ui.widgets import (
    PasswordField, StrengthMeter, RuleChecklist, run_in_background, set_busy, set_error, logo_pixmap,
)


def _header(layout: QVBoxLayout, title: str, subtitle: str = ""):
    t = QLabel(title)
    t.setObjectName("DialogTitle")
    layout.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("Subtitle")
        s.setWordWrap(True)
        layout.addWidget(s)
    layout.addSpacing(6)


def _field(layout: QVBoxLayout, label: str, widget):
    lbl = QLabel(label.upper())
    lbl.setObjectName("FieldLabel")
    layout.addWidget(lbl)
    layout.addWidget(widget)


def _error_label() -> QLabel:
    lbl = QLabel()
    lbl.setObjectName("Error")
    lbl.setWordWrap(True)
    lbl.hide()
    return lbl


def _show_error(lbl: QLabel, message: str):
    lbl.setText(message)
    lbl.setVisible(bool(message))


class _BaseDialog(QDialog):
    def __init__(self, parent=None, width: int = 440):
        super().__init__(parent)
        self.setMinimumWidth(width)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(28, 24, 28, 24)
        self.body.setSpacing(8)


def save_recovery_file_dialog(parent, username: str, recovery_key: str) -> bool:
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save Encrypted Recovery File",
        f"{username}_recovery{recovery_mod.RECOVERY_FILE_EXT}", recovery_mod.RECOVERY_FILE_FILTER,
    )
    if not path:
        return False
    if not path.lower().endswith(recovery_mod.RECOVERY_FILE_EXT):
        path += recovery_mod.RECOVERY_FILE_EXT
    try:
        recovery_mod.write_recovery_file(path, username, recovery_key)
    except OSError as e:
        QMessageBox.critical(parent, "Could not save", f"Failed to save the recovery file:\n{e}")
        return False
    QMessageBox.information(
        parent, "Recovery file saved",
        f"Encrypted recovery file saved to:\n{path}\n\n"
        "Move it to a USB drive or another safe offline place.",
    )
    return True


class RecoveryKeyDialog(_BaseDialog):
    """Shown once at registration (or key rotation). The user must confirm
    they saved the key before continuing."""

    def __init__(self, recovery_key: str, username: str, parent=None):
        super().__init__(parent, width=560)
        self.setWindowTitle("Save Your Recovery Key")
        self._recovery_key = recovery_key
        self._username = username

        _header(self.body, "Save your recovery key",
                "This is the only way back into your vault if you forget your master password. "
                "It will not be shown again.")

        box = QFrame()
        box.setObjectName("FieldBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(16, 14, 16, 14)
        key_label = QLabel(recovery_key)
        key_label.setObjectName("Mono")
        key_label.setWordWrap(True)
        key_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box_layout.addWidget(key_label)
        self.body.addWidget(box)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Encrypted Recovery File...")
        save_btn.clicked.connect(self._save_to_file)
        copy_btn = QPushButton("Copy Key")
        copy_btn.setObjectName("Secondary")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(save_btn, 2)
        btn_row.addWidget(copy_btn, 1)
        self.body.addLayout(btn_row)

        warn = QLabel("Anyone with this key (or the recovery file) and your username can reset your "
                      "master password. Keep it offline and private.")
        warn.setObjectName("Warning")
        warn.setWordWrap(True)
        self.body.addWidget(warn)

        self.ack_checkbox = QCheckBox("I have saved my recovery key somewhere safe")
        self.body.addSpacing(4)
        self.body.addWidget(self.ack_checkbox)

        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.accept)
        self.ack_checkbox.toggled.connect(self.continue_btn.setEnabled)
        self.body.addWidget(self.continue_btn)

    def _save_to_file(self):
        if save_recovery_file_dialog(self, self._username, self._recovery_key):
            self.ack_checkbox.setChecked(True)

    def _copy(self):
        shared_clipboard_guard().copy(self._recovery_key)
        self.copy_feedback()

    def copy_feedback(self):
        self.ack_checkbox.setText("I have saved my recovery key somewhere safe  (copied - clipboard clears in 25s)")

    def reject(self):
        # Esc and the window close button both route through reject().
        if not self.ack_checkbox.isChecked():
            resp = QMessageBox.warning(
                self, "Recovery key not saved",
                "If you continue without saving your recovery key and later forget your "
                "master password, your vault cannot be recovered.\n\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
        super().reject()


class TwoFactorPromptDialog(_BaseDialog):
    """Prompts for a 6-digit TOTP code during login; submits automatically at 6 digits."""

    def __init__(self, parent=None):
        super().__init__(parent, width=380)
        self.setWindowTitle("Two-Factor Authentication")
        _header(self.body, "Two-factor authentication", "Enter the 6-digit code from your authenticator app.")
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("123456")
        self.code_edit.setAlignment(Qt.AlignCenter)
        self.code_edit.setStyleSheet("font-size: 22px; letter-spacing: 6px;")
        self.code_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,6}")))
        self.code_edit.textChanged.connect(lambda t: len(t) == 6 and self.accept())
        self.code_edit.returnPressed.connect(self.accept)
        self.body.addWidget(self.code_edit)
        btn = QPushButton("Verify")
        btn.clicked.connect(self.accept)
        self.body.addWidget(btn)

    @staticmethod
    def get_code(parent=None):
        dlg = TwoFactorPromptDialog(parent)
        if dlg.exec() == QDialog.Accepted and dlg.code_edit.text().strip():
            return dlg.code_edit.text().strip()
        return None


class TwoFactorSetupDialog(_BaseDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent, width=420)
        self.session = session
        self.setWindowTitle("Set Up Two-Factor Authentication")

        self.secret = totp_mod.generate_secret()
        qr_bytes = totp_mod.make_qr_png_bytes(self.secret, session.username)

        _header(self.body, "Enable two-factor authentication",
                "1. Scan this QR code with Google Authenticator, Authy or Microsoft Authenticator.")

        qr_frame = QFrame()
        qr_frame.setStyleSheet("background: white; border-radius: 14px;")
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setContentsMargins(10, 10, 10, 10)
        qr_label = QLabel()
        pix = QPixmap()
        pix.loadFromData(qr_bytes)
        qr_label.setPixmap(pix.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_label.setAlignment(Qt.AlignCenter)
        qr_layout.addWidget(qr_label)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(qr_frame)
        row.addStretch()
        self.body.addLayout(row)

        manual = QLabel("Can't scan? Enter this key manually:")
        manual.setObjectName("Muted")
        self.body.addWidget(manual)
        grouped = " ".join(self.secret[i:i + 4] for i in range(0, len(self.secret), 4))
        secret_label = QLabel(grouped)
        secret_label.setObjectName("Mono")
        secret_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.addWidget(secret_label)

        self.body.addSpacing(6)
        step2 = QLabel("2. Enter the 6-digit code shown in the app to confirm:")
        step2.setObjectName("Subtitle")
        self.body.addWidget(step2)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("123456")
        self.code_edit.setAlignment(Qt.AlignCenter)
        self.code_edit.setStyleSheet("font-size: 20px; letter-spacing: 6px;")
        self.code_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"\d{0,6}")))
        self.code_edit.returnPressed.connect(self._confirm)
        self.body.addWidget(self.code_edit)

        self.error = _error_label()
        self.body.addWidget(self.error)

        confirm_btn = QPushButton("Enable 2FA")
        confirm_btn.clicked.connect(self._confirm)
        self.body.addWidget(confirm_btn)

    def _confirm(self):
        try:
            totp_mod.enable_2fa(self.session, self.secret, self.code_edit.text())
        except ValueError as e:
            _show_error(self.error, str(e))
            self.code_edit.selectAll()
            return
        self.accept()


class ConfirmPasswordDialog(_BaseDialog):
    """Re-authenticates the user before a sensitive action."""

    def __init__(self, session, message: str, parent=None):
        super().__init__(parent, width=420)
        self.session = session
        self.setWindowTitle("Confirm Master Password")
        _header(self.body, "Confirm it's you", message)
        self.password = PasswordField("Master password")
        self.password.edit.returnPressed.connect(self._submit)
        self.body.addWidget(self.password)
        self.error = _error_label()
        self.body.addWidget(self.error)
        self.submit_btn = QPushButton("Confirm")
        self.submit_btn.clicked.connect(self._submit)
        self.body.addWidget(self.submit_btn)

    def _submit(self):
        if not self.password.text():
            return
        set_busy(self.submit_btn, True, "Verifying...")
        pw = self.password.text()
        run_in_background(lambda: auth_mod.verify_master_password(self.session, pw), self._done, self._failed)

    def _done(self, ok: bool):
        set_busy(self.submit_btn, False)
        if ok:
            self.accept()
        else:
            _show_error(self.error, "Incorrect master password.")
            self.password.edit.selectAll()
            self.password.edit.setFocus()

    def _failed(self, error):
        set_busy(self.submit_btn, False)
        _show_error(self.error, str(error))

    @staticmethod
    def confirm(session, message: str, parent=None) -> bool:
        return ConfirmPasswordDialog(session, message, parent).exec() == QDialog.Accepted


class ChangePasswordDialog(_BaseDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent, width=460)
        self.session = session
        self.setWindowTitle("Change Master Password")
        _header(self.body, "Change master password", "Your vault stays encrypted; only the key wrapping changes.")

        self.current_pw = PasswordField("Current master password")
        self.new_pw = PasswordField("New master password")
        self.confirm_pw = PasswordField("Confirm new password")
        _field(self.body, "Current password", self.current_pw)
        _field(self.body, "New password", self.new_pw)
        self.meter = StrengthMeter()
        self.body.addWidget(self.meter)
        _field(self.body, "Confirm new password", self.confirm_pw)

        self.rules = RuleChecklist(lambda: session.username, self.new_pw.edit, self.confirm_pw.edit)
        self.body.addWidget(self.rules)
        self.new_pw.edit.textChanged.connect(lambda t: self.meter.update_for(t, [session.username]))

        self.error = _error_label()
        self.body.addWidget(self.error)

        self.submit_btn = QPushButton("Change Password")
        self.submit_btn.clicked.connect(self._submit)
        self.rules.changed.connect(self.submit_btn.setEnabled)
        self.submit_btn.setEnabled(self.rules.is_valid())
        self.body.addWidget(self.submit_btn)

    def _submit(self):
        if not self.rules.is_valid():
            return
        set_busy(self.submit_btn, True, "Updating...")
        current, new = self.current_pw.text(), self.new_pw.text()
        run_in_background(
            lambda: auth_mod.change_master_password(self.session, current, new),
            self._done, self._failed,
        )

    def _done(self, _):
        set_busy(self.submit_btn, False)
        self.accept()

    def _failed(self, error):
        set_busy(self.submit_btn, False)
        _show_error(self.error, str(error))


class PasswordGeneratorDialog(_BaseDialog):
    def __init__(self, parent=None, on_use=None, user_inputs=None):
        super().__init__(parent, width=460)
        self.setWindowTitle("Password Generator")
        self.on_use = on_use
        self.user_inputs = user_inputs or []
        _header(self.body, "Generate a strong password")

        box = QFrame()
        box.setObjectName("FieldBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(16, 14, 16, 14)
        self.result_label = QLabel()
        self.result_label.setObjectName("Mono")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.result_label.setStyleSheet("font-size: 17px;")
        box_layout.addWidget(self.result_label)
        self.meter = StrengthMeter()
        box_layout.addWidget(self.meter)
        self.body.addWidget(box)

        length_row = QHBoxLayout()
        length_lbl = QLabel("LENGTH")
        length_lbl.setObjectName("FieldLabel")
        self.length_value = QLabel()
        self.length_value.setStyleSheet("font-weight: 700;")
        length_row.addWidget(length_lbl)
        length_row.addStretch()
        length_row.addWidget(self.length_value)
        self.body.addSpacing(6)
        self.body.addLayout(length_row)
        self.length_slider = QSlider(Qt.Horizontal)
        self.length_slider.setRange(8, 64)
        self.length_slider.setValue(20)
        self.body.addWidget(self.length_slider)

        grid = QGridLayout()
        self.upper_cb = QCheckBox("Uppercase (A-Z)")
        self.lower_cb = QCheckBox("Lowercase (a-z)")
        self.digits_cb = QCheckBox("Numbers (0-9)")
        self.symbols_cb = QCheckBox("Symbols (!@#...)")
        for i, cb in enumerate((self.upper_cb, self.lower_cb, self.digits_cb, self.symbols_cb)):
            cb.setChecked(True)
            cb.toggled.connect(self._on_option_toggled)
            grid.addWidget(cb, i // 2, i % 2)
        self.body.addLayout(grid)
        self.length_slider.valueChanged.connect(self._generate)

        btn_row = QHBoxLayout()
        regen_btn = QPushButton("Regenerate")
        regen_btn.setObjectName("Secondary")
        regen_btn.clicked.connect(self._generate)
        copy_btn = QPushButton("Copy")
        copy_btn.setObjectName("Secondary")
        copy_btn.clicked.connect(lambda: shared_clipboard_guard().copy(self._password))
        btn_row.addWidget(regen_btn)
        btn_row.addWidget(copy_btn)
        if self.on_use:
            use_btn = QPushButton("Use Password")
            use_btn.clicked.connect(self._use)
            btn_row.addWidget(use_btn)
        self.body.addSpacing(6)
        self.body.addLayout(btn_row)

        self._password = ""
        self._generate()

    def _on_option_toggled(self, checked: bool):
        boxes = (self.upper_cb, self.lower_cb, self.digits_cb, self.symbols_cb)
        if not any(cb.isChecked() for cb in boxes):
            self.sender().setChecked(True)  # keep at least one character set
            return
        self._generate()

    def _generate(self):
        self.length_value.setText(str(self.length_slider.value()))
        self._password = vault.generate_password(
            length=self.length_slider.value(),
            use_upper=self.upper_cb.isChecked(),
            use_lower=self.lower_cb.isChecked(),
            use_digits=self.digits_cb.isChecked(),
            use_symbols=self.symbols_cb.isChecked(),
        )
        self.result_label.setText(self._password)
        self.meter.update_for(self._password, self.user_inputs)

    def _use(self):
        if self.on_use:
            self.on_use(self._password)
        self.accept()


class ItemEditorDialog(_BaseDialog):
    def __init__(self, parent=None, item: vault.VaultItem = None):
        super().__init__(parent, width=500)
        self.item = item
        self.setWindowTitle("Edit Entry" if item else "New Entry")
        _header(self.body, "Edit entry" if item else "New entry",
                "Everything here is encrypted with AES-256-GCM before it is saved.")

        self.title_edit = QLineEdit(item.title if item else "")
        self.title_edit.setPlaceholderText("e.g. Gmail")
        self.site_edit = QLineEdit(item.website_or_app if item else "")
        self.site_edit.setPlaceholderText("e.g. mail.google.com or Spotify app")
        self.username_edit = QLineEdit(item.username if item else "")
        self.username_edit.setPlaceholderText("you@example.com")

        self.password = PasswordField("Password")
        self.password.setText(item.password if item else "")
        gen_btn = QPushButton("Generate")
        gen_btn.setObjectName("Small")
        gen_btn.setFocusPolicy(Qt.NoFocus)
        gen_btn.clicked.connect(self._open_generator)
        self.password.layout().addWidget(gen_btn)

        self.meter = StrengthMeter()
        self.password.edit.textChanged.connect(self._update_meter)

        self.notes_edit = QPlainTextEdit(item.notes if item else "")
        self.notes_edit.setPlaceholderText("Optional: security questions, recovery codes, PINs...")
        self.notes_edit.setFixedHeight(90)

        _field(self.body, "Title", self.title_edit)
        _field(self.body, "Website / App", self.site_edit)
        _field(self.body, "Username / Email", self.username_edit)
        _field(self.body, "Password", self.password)
        self.body.addWidget(self.meter)
        _field(self.body, "Notes", self.notes_edit)

        self.error = _error_label()
        self.body.addWidget(self.error)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("Secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Entry")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        self.body.addSpacing(6)
        self.body.addLayout(btn_row)

        self._update_meter()
        self.title_edit.setFocus()

    def _update_meter(self, *_):
        self.meter.update_for(self.password.text(), [self.username_edit.text(), self.title_edit.text()])

    def _open_generator(self):
        PasswordGeneratorDialog(self, on_use=self.password.setText).exec()

    def _save(self):
        problems = []
        no_name = not self.title_edit.text().strip() and not self.site_edit.text().strip()
        set_error(self.title_edit, no_name)
        set_error(self.site_edit, no_name)
        if no_name:
            problems.append("Enter a title or a website/app name.")
        no_password = not self.password.text()
        set_error(self.password.edit, no_password)
        if no_password:
            problems.append("Enter a password (or use Generate).")
        if problems:
            _show_error(self.error, "\n".join(problems))
            return
        self.accept()

    def get_item(self) -> vault.VaultItem:
        return vault.VaultItem(
            id=self.item.id if self.item else None,
            title=self.title_edit.text().strip(),
            website_or_app=self.site_edit.text().strip(),
            username=self.username_edit.text().strip(),
            password=self.password.text(),
            notes=self.notes_edit.toPlainText().strip(),
        )


class AutoLockDialog(_BaseDialog):
    def __init__(self, current_minutes: int, parent=None):
        super().__init__(parent, width=380)
        self.setWindowTitle("Auto-Lock")
        _header(self.body, "Auto-lock timer", "Lock the vault automatically after a period of inactivity.")
        self.spin = QSpinBox()
        self.spin.setRange(1, 60)
        self.spin.setSuffix(" minutes")
        self.spin.setValue(current_minutes)
        self.body.addWidget(self.spin)
        btn = QPushButton("Save")
        btn.clicked.connect(self.accept)
        self.body.addSpacing(6)
        self.body.addWidget(btn)

    def minutes(self) -> int:
        return self.spin.value()
