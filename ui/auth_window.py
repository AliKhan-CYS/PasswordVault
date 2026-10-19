"""Login / Create Account / Forgot Password screen."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabBar, QStackedWidget,
    QComboBox, QFrame, QFileDialog, QGraphicsDropShadowEffect, QScrollArea, QMessageBox, QSizePolicy,
)

from app import db, auth, brands, recovery as recovery_mod
from app.auth import AuthError, TwoFactorRequiredError
from ui.dialogs import RecoveryKeyDialog, TwoFactorPromptDialog
from ui.styles import ACCENT_2, MUTED
from ui.widgets import (
    PasswordField, StrengthMeter, RuleChecklist, run_in_background, set_busy, set_error,
    logo_pixmap, shake, entry_icon_pixmap,
)


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


def _tab_page() -> tuple[QWidget, QVBoxLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(2, 14, 2, 2)
    layout.setSpacing(6)
    return page, layout


class AuthWindow(QWidget):
    authenticated = Signal(object)  # Session

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AuthPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()

    # ---------- layout ----------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        content.setAutoFillBackground(False)  # setWidget() turns it on, which paints the default grey
        row = QHBoxLayout(content)
        row.setContentsMargins(40, 16, 40, 16)
        row.addStretch(1)
        row.addWidget(self._build_hero(), 0, Qt.AlignVCenter)
        row.addSpacing(70)
        row.addWidget(self._build_card(), 0, Qt.AlignVCenter)
        row.addStretch(1)

    def _build_hero(self) -> QWidget:
        hero = QWidget()
        hero.setFixedWidth(420)
        layout = QVBoxLayout(hero)
        layout.setSpacing(14)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(84))
        layout.addWidget(logo)

        title = QLabel("SecureVault")
        title.setStyleSheet("font-size: 44px; font-weight: 800; color: white;")
        layout.addWidget(title)

        tagline = QLabel(f"All your passwords.<br><span style='color:{ACCENT_2}'>Safe in one place.</span>")
        tagline.setStyleSheet("font-size: 22px; font-weight: 600; color: #e9ebf8;")
        tagline.setWordWrap(True)
        layout.addWidget(tagline)
        layout.addSpacing(10)

        for headline, detail in (
            ("Everything in one place", "Banks, wallets, email, Netflix, Spotify and more, neatly sorted."),
            ("Only you can open it", "One master password opens your vault. Nobody else can."),
            ("Extra lock with your phone", "Turn on a login code from your phone for even more safety."),
            ("Never get locked out", "Forgot your password? Your backup key gets you back in."),
        ):
            item = QLabel(
                f"<span style='color:{ACCENT_2}; font-size:15px'>&#10003;</span>&nbsp;&nbsp;"
                f"<b style='color:white'>{headline}</b><br>"
                f"<span style='color:{MUTED}'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{detail}</span>"
            )
            item.setStyleSheet("font-size: 14px;")
            layout.addWidget(item)

        layout.addSpacing(12)
        works = QLabel("WORKS WITH ALL YOUR ACCOUNTS")
        works.setObjectName("FieldLabel")
        layout.addWidget(works)
        strip = QHBoxLayout()
        strip.setSpacing(10)
        for key in ("hbl", "meezan", "jazzcash", "easypaisa", "gmail", "netflix", "spotify", "daraz"):
            logo_lbl = QLabel()
            brand = brands.BRAND_BY_KEY[key]
            logo_lbl.setPixmap(entry_icon_pixmap(brand.name, brand, 38))
            logo_lbl.setToolTip(brand.name)
            strip.addWidget(logo_lbl)
        strip.addStretch()
        layout.addLayout(strip)
        return hero

    def _build_card(self) -> QFrame:
        self.card = QFrame()
        self.card.setObjectName("Card")
        self.card.setFixedWidth(470)
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(34, 26, 34, 26)
        layout.setSpacing(4)

        heading = QLabel("Welcome back")
        heading.setObjectName("Title")
        self.card_heading = heading
        sub = QLabel("Unlock your vault to continue.")
        sub.setObjectName("Subtitle")
        self.card_sub = sub
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addSpacing(6)

        self.tabs = QTabBar()
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.pages = QStackedWidget()
        for page, label in ((self._build_login_tab(), "Log In"),
                            (self._build_register_tab(), "Create Account"),
                            (self._build_recovery_tab(), "Forgot Password")):
            self.tabs.addTab(label)
            self.pages.addWidget(page)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages)
        self._fit_to_tab(0)
        return self.card

    def _fit_to_tab(self, index: int):
        # Hidden pages are ignored for sizing, so the card hugs the visible form.
        self.pages.setCurrentIndex(index)
        for i in range(self.pages.count()):
            policy = QSizePolicy.Preferred if i == index else QSizePolicy.Ignored
            self.pages.widget(i).setSizePolicy(policy, policy)
        self.pages.updateGeometry()

    def _on_tab_changed(self, index: int):
        self._fit_to_tab(index)
        heading, sub = [
            ("Welcome back", "Unlock your vault to continue."),
            ("Create your vault", "Choose one strong password you'll remember. It unlocks everything."),
            ("Get back in", "Use the backup key you saved when you signed up."),
        ][index]
        self.card_heading.setText(heading)
        self.card_sub.setText(sub)
        self.card_sub.setWordWrap(True)
        focus = [self.login_password.edit, self.reg_username, self.rec_username][index]
        if index == 0 and not self.login_username.currentText():
            focus = self.login_username
        focus.setFocus()

    # ---------- Log in ----------

    def _build_login_tab(self) -> QWidget:
        page, layout = _tab_page()
        self.login_username = QComboBox()
        self.login_username.setEditable(True)
        self.login_username.lineEdit().setPlaceholderText("Username")
        self.login_password = PasswordField("Master password")
        self.login_password.edit.returnPressed.connect(self._do_login)
        self.login_username.lineEdit().returnPressed.connect(self.login_password.edit.setFocus)

        _field(layout, "Username", self.login_username)
        layout.addSpacing(4)
        _field(layout, "Master password", self.login_password)
        layout.addSpacing(6)
        self.login_error = _error_label()
        layout.addWidget(self.login_error)

        self.login_btn = QPushButton("Unlock Vault")
        self.login_btn.setMinimumHeight(44)
        self.login_btn.clicked.connect(lambda: self._do_login())
        layout.addWidget(self.login_btn)

        forgot = QPushButton("Forgot your master password?")
        forgot.setObjectName("Ghost")
        forgot.clicked.connect(lambda: self.tabs.setCurrentIndex(2))
        layout.addWidget(forgot, 0, Qt.AlignCenter)
        layout.addStretch()
        self.refresh_usernames()
        return page

    def _do_login(self, totp_code: str = None):
        username = self.login_username.currentText().strip()
        password = self.login_password.text()
        set_error(self.login_username.lineEdit(), not username)
        set_error(self.login_password.edit, not password)
        if not username or not password:
            _show_error(self.login_error, "Enter your username and master password.")
            return
        _show_error(self.login_error, "")
        set_busy(self.login_btn, True, "Unlocking...")
        run_in_background(
            lambda: auth.login(username, password, totp_code=totp_code),
            self._login_ok, self._login_failed,
        )

    def _login_ok(self, session):
        set_busy(self.login_btn, False)
        self.login_password.clear()
        _show_error(self.login_error, "")
        self.authenticated.emit(session)

    def _login_failed(self, error):
        set_busy(self.login_btn, False)
        if isinstance(error, TwoFactorRequiredError):
            code = TwoFactorPromptDialog.get_code(self)
            if code:
                self._do_login(totp_code=code)
            return
        message = str(error) if isinstance(error, AuthError) else f"Unexpected error: {error}"
        _show_error(self.login_error, message)
        set_error(self.login_password.edit, True)
        self.login_password.edit.selectAll()
        self.login_password.edit.setFocus()
        shake(self.card)

    # ---------- Create account ----------

    def _build_register_tab(self) -> QWidget:
        page, layout = _tab_page()
        self.reg_username = QLineEdit()
        self.reg_username.setPlaceholderText("Choose a username")
        self.reg_password = PasswordField("Master password")
        self.reg_confirm = PasswordField("Repeat master password")
        self.reg_meter = StrengthMeter()

        _field(layout, "Username", self.reg_username)
        layout.addSpacing(4)
        _field(layout, "Master password", self.reg_password)
        layout.addWidget(self.reg_meter)
        _field(layout, "Confirm password", self.reg_confirm)

        self.reg_rules = RuleChecklist(lambda: self.reg_username.text(), self.reg_password.edit, self.reg_confirm.edit)
        layout.addWidget(self.reg_rules)

        self.reg_error = _error_label()
        layout.addWidget(self.reg_error)
        self.reg_btn = QPushButton("Create Account")
        self.reg_btn.setMinimumHeight(44)
        self.reg_btn.clicked.connect(self._do_register)
        layout.addWidget(self.reg_btn)
        layout.addStretch()

        self.reg_username.textChanged.connect(self._refresh_register_state)
        self.reg_password.edit.textChanged.connect(self._refresh_register_state)
        self.reg_confirm.edit.textChanged.connect(self._refresh_register_state)
        self.reg_username.returnPressed.connect(self.reg_password.edit.setFocus)
        self.reg_password.edit.returnPressed.connect(self.reg_confirm.edit.setFocus)
        self.reg_confirm.edit.returnPressed.connect(self._do_register)
        self._refresh_register_state()
        return page

    def _refresh_register_state(self, *_):
        username = self.reg_username.text().strip()
        self.reg_meter.update_for(self.reg_password.text(), [username] if username else None)
        valid = self.reg_rules.refresh()
        self.reg_btn.setEnabled(bool(username) and valid)

    def _do_register(self):
        username = self.reg_username.text().strip()
        password = self.reg_password.text()
        if not username or not self.reg_rules.is_valid():
            return
        _show_error(self.reg_error, "")
        set_busy(self.reg_btn, True, "Creating your vault...")
        run_in_background(lambda: auth.register_user(username, password), self._register_ok, self._register_failed)

    def _register_ok(self, result):
        set_busy(self.reg_btn, False)
        session, recovery_key = result
        self.reg_username.clear()
        self.reg_password.clear()
        self.reg_confirm.clear()
        self.refresh_usernames(select=session.username)
        RecoveryKeyDialog(recovery_key, session.username, self).exec()
        self.tabs.setCurrentIndex(0)
        self.authenticated.emit(session)

    def _register_failed(self, error):
        set_busy(self.reg_btn, False)
        self._refresh_register_state()
        _show_error(self.reg_error, str(error) if isinstance(error, AuthError) else f"Unexpected error: {error}")
        shake(self.card)

    # ---------- Forgot password ----------

    def _build_recovery_tab(self) -> QWidget:
        page, layout = _tab_page()

        load_btn = QPushButton("Open Backup Key File...")
        load_btn.setObjectName("Secondary")
        load_btn.setMinimumHeight(40)
        load_btn.clicked.connect(self._load_recovery_file)
        layout.addWidget(load_btn)
        self.rec_file_status = QLabel("or type your username and backup key below")
        self.rec_file_status.setObjectName("Muted")
        self.rec_file_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rec_file_status)
        layout.addSpacing(4)

        self.rec_username = QLineEdit()
        self.rec_username.setPlaceholderText("Username")
        self.rec_key = PasswordField("XXXX-XXXX-XXXX-...")
        self.rec_new = PasswordField("New master password")
        self.rec_confirm = PasswordField("Repeat new master password")

        _field(layout, "Username", self.rec_username)
        _field(layout, "Backup key", self.rec_key)
        _field(layout, "New master password", self.rec_new)
        _field(layout, "Confirm new password", self.rec_confirm)

        self.rec_rules = RuleChecklist(lambda: self.rec_username.text(), self.rec_new.edit, self.rec_confirm.edit)
        layout.addWidget(self.rec_rules)

        self.rec_error = _error_label()
        layout.addWidget(self.rec_error)
        self.rec_btn = QPushButton("Reset Master Password")
        self.rec_btn.setMinimumHeight(44)
        self.rec_btn.clicked.connect(self._do_recover)
        layout.addWidget(self.rec_btn)
        layout.addStretch()

        for edit in (self.rec_username, self.rec_key.edit, self.rec_new.edit, self.rec_confirm.edit):
            edit.textChanged.connect(self._refresh_recover_state)
        self.rec_confirm.edit.returnPressed.connect(self._do_recover)
        self._refresh_recover_state()
        return page

    def _refresh_recover_state(self, *_):
        valid = self.rec_rules.refresh()
        self.rec_btn.setEnabled(bool(self.rec_username.text().strip() and self.rec_key.text().strip()) and valid)

    def _load_recovery_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Backup Key File", "",
            f"{recovery_mod.RECOVERY_FILE_FILTER};;Older backup key file (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            data = recovery_mod.read_recovery_file(path)
        except (AuthError, OSError) as e:
            _show_error(self.rec_error, str(e) if isinstance(e, AuthError) else "Could not open that file.")
            shake(self.card)
            return
        self.rec_username.setText(data["username"])
        self.rec_key.setText(data["recovery_key"])
        self.rec_file_status.setText(f"<span style='color:#22c55e'>&#10003; Backup key loaded for "
                                     f"<b>{data['username']}</b></span>")
        self.rec_file_status.setTextFormat(Qt.RichText)
        _show_error(self.rec_error, "")
        self.rec_new.edit.setFocus()

    def _do_recover(self):
        username = self.rec_username.text().strip()
        key = self.rec_key.text()
        new_pw = self.rec_new.text()
        if not username or not key.strip() or not self.rec_rules.is_valid():
            return
        _show_error(self.rec_error, "")
        set_busy(self.rec_btn, True, "Resetting...")
        run_in_background(lambda: auth.recover_account(username, key, new_pw), self._recover_ok, self._recover_failed)

    def _recover_ok(self, session):
        set_busy(self.rec_btn, False)
        for field in (self.rec_key, self.rec_new, self.rec_confirm):
            field.clear()
        self.rec_username.clear()
        self.rec_file_status.setText("or type your username and backup key below")
        QMessageBox.information(
            self, "Password reset",
            "Your master password has been reset and your vault is unlocked.\n\n"
            "Your backup key still works. For extra safety you can create a new one "
            "from Settings > New Backup Key.",
        )
        self.tabs.setCurrentIndex(0)
        self.authenticated.emit(session)

    def _recover_failed(self, error):
        set_busy(self.rec_btn, False)
        self._refresh_recover_state()
        _show_error(self.rec_error, str(error) if isinstance(error, AuthError) else f"Unexpected error: {error}")
        shake(self.card)

    # ---------- public ----------

    def refresh_usernames(self, select: str = None):
        current = select or self.login_username.currentText()
        self.login_username.clear()
        self.login_username.addItems(db.list_usernames())
        if current:
            self.login_username.setCurrentText(current)

    def focus_login(self):
        self.tabs.setCurrentIndex(0)
        self._on_tab_changed(0)
