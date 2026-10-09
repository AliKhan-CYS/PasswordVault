"""Main vault window: list, search, add/edit/delete entries, settings."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QMenu, QSpinBox, QFormLayout,
    QDialog, QFileDialog
)

from app import vault, totp as totp_mod, recovery as recovery_mod, db
from app.auth import Session
from ui.dialogs import ItemEditorDialog, PasswordGeneratorWidget, TwoFactorSetupDialog, \
    ChangePasswordDialog, RecoveryKeyDialog
from ui.security import ClipboardGuard


class MainWindow(QWidget):
    locked = Signal()

    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.clipboard_guard = ClipboardGuard(seconds=25)
        self.setWindowTitle(f"SecureVaultPM — {session.username}")
        self.setMinimumSize(640, 480)
        self._build_ui()
        self._reload_items()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        top_row = QHBoxLayout()
        title = QLabel(f"Vault — {self.session.username}")
        title.setObjectName("TitleLabel")
        top_row.addWidget(title)
        top_row.addStretch()

        settings_btn = QPushButton("Settings")
        settings_btn.setObjectName("SecondaryButton")
        settings_btn.clicked.connect(self._open_settings_menu)
        top_row.addWidget(settings_btn)

        lock_btn = QPushButton("Lock")
        lock_btn.setObjectName("SecondaryButton")
        lock_btn.clicked.connect(self.locked.emit)
        top_row.addWidget(lock_btn)

        layout.addLayout(top_row)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by title, site, or username...")
        self.search_edit.textChanged.connect(self._reload_items)
        add_btn = QPushButton("+ Add Entry")
        add_btn.clicked.connect(self._add_entry)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(add_btn)
        layout.addLayout(search_row)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._edit_selected)
        layout.addWidget(self.list_widget)

        action_row = QHBoxLayout()
        copy_user_btn = QPushButton("Copy Username")
        copy_user_btn.setObjectName("SecondaryButton")
        copy_user_btn.clicked.connect(lambda: self._copy_field("username"))
        copy_pw_btn = QPushButton("Copy Password")
        copy_pw_btn.clicked.connect(lambda: self._copy_field("password"))
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("SecondaryButton")
        edit_btn.clicked.connect(self._edit_selected)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self._delete_selected)
        action_row.addWidget(copy_user_btn)
        action_row.addWidget(copy_pw_btn)
        action_row.addWidget(edit_btn)
        action_row.addWidget(delete_btn)
        layout.addLayout(action_row)

    def _reload_items(self):
        query = self.search_edit.text() if hasattr(self, "search_edit") else ""
        self._items = vault.search_items(self.session, query)
        self.list_widget.clear()
        for it in self._items:
            label = f"{it.title or it.website_or_app}   —   {it.username}"
            list_item = QListWidgetItem(label)
            list_item.setData(Qt.UserRole, it.id)
            self.list_widget.addItem(list_item)

    def _selected_item(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _add_entry(self):
        dlg = ItemEditorDialog(self)
        if dlg.exec() == QDialog.Accepted:
            new_item = dlg.get_item()
            if not new_item.title and not new_item.website_or_app:
                QMessageBox.warning(self, "Missing info", "Please provide a title or website/app name.")
                return
            vault.add_item(self.session, new_item)
            self._reload_items()

    def _edit_selected(self):
        item = self._selected_item()
        if not item:
            return
        dlg = ItemEditorDialog(self, item=item)
        if dlg.exec() == QDialog.Accepted:
            updated = dlg.get_item()
            vault.update_item(self.session, updated)
            self._reload_items()

    def _delete_selected(self):
        item = self._selected_item()
        if not item:
            return
        resp = QMessageBox.question(
            self, "Delete entry", f"Delete '{item.title or item.website_or_app}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            vault.delete_item(item.id)
            self._reload_items()

    def _copy_field(self, field: str):
        item = self._selected_item()
        if not item:
            QMessageBox.information(self, "No selection", "Select an entry first.")
            return
        value = getattr(item, field)
        self.clipboard_guard.copy(value)
        QMessageBox.information(self, "Copied", f"{field.capitalize()} copied. Clipboard clears in 25s.")

    # ---------- settings ----------

    def _open_settings_menu(self):
        menu = QMenu(self)
        menu.addAction("Change Master Password", self._change_password)
        if self.session_totp_enabled():
            menu.addAction("Disable Two-Factor Authentication", self._disable_2fa)
        else:
            menu.addAction("Enable Two-Factor Authentication", self._enable_2fa)
        menu.addAction("Regenerate Recovery Key", self._regenerate_recovery)
        menu.addAction("Auto-Lock Timer...", self._configure_auto_lock)
        menu.exec(self.mapToGlobal(self.rect().bottomRight()))

    def session_totp_enabled(self) -> bool:
        user = db.get_user_by_id(self.session.user_id)
        return bool(user and user["totp_enabled"])

    def _change_password(self):
        ChangePasswordDialog(self.session, self).exec()

    def _enable_2fa(self):
        TwoFactorSetupDialog(self.session, self).exec()

    def _disable_2fa(self):
        resp = QMessageBox.question(
            self, "Disable 2FA", "Are you sure you want to disable two-factor authentication?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            totp_mod.disable_2fa(self.session)
            QMessageBox.information(self, "Disabled", "Two-factor authentication disabled.")

    def _regenerate_recovery(self):
        resp = QMessageBox.question(
            self, "Regenerate Recovery Key",
            "This will invalidate your old recovery key. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        new_key = recovery_mod.regenerate_recovery_key(self.session)
        RecoveryKeyDialog(new_key, self.session.username, self).exec()

    def _configure_auto_lock(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Auto-Lock Timer")
        form = QFormLayout(dlg)
        spin = QSpinBox()
        spin.setRange(1, 60)
        user = db.get_user_by_id(self.session.user_id)
        spin.setValue(user["auto_lock_minutes"] if user else 5)
        form.addRow("Lock after (minutes of inactivity)", spin)
        btn = QPushButton("Save")
        form.addRow(btn)

        def save():
            db.set_auto_lock_minutes(self.session.user_id, spin.value())
            main_win = self.window()
            if hasattr(main_win, "apply_auto_lock_minutes"):
                main_win.apply_auto_lock_minutes(spin.value())
            dlg.accept()

        btn.clicked.connect(save)
        dlg.exec()
