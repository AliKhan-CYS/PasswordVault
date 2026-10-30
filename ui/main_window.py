"""Main vault screen: header, searchable entry list and a detail panel."""

import datetime
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal, QPoint, QRectF, QSize, QUrl
from PySide6.QtGui import QColor, QPainter, QKeySequence, QShortcut, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QMessageBox, QMenu, QDialog, QFrame, QSplitter, QStackedWidget,
    QStyledItemDelegate, QStyle, QScrollArea, QApplication,
)

from app import vault, totp as totp_mod, recovery as recovery_mod, db, brands
from app.auth import Session
from ui.dialogs import (
    ItemEditorDialog, PasswordGeneratorDialog, TwoFactorSetupDialog, ChangePasswordDialog,
    RecoveryKeyDialog, ConfirmPasswordDialog, AutoLockDialog, AboutDialog,
)
from ui.security import shared_clipboard_guard
from ui.styles import ACCENT, BRAND_BLUE, MUTED, SURFACE_2
from ui.widgets import (
    StrengthMeter, Toast, logo_pixmap, avatar_pixmap, run_in_background, fade_in,
    draw_entry_icon, entry_icon_pixmap, draw_symbol_tile,
)

ITEM_ID_ROLE = Qt.UserRole
TITLE_ROLE = Qt.UserRole + 1
SUBTITLE_ROLE = Qt.UserRole + 2
BRAND_ROLE = Qt.UserRole + 3
COUNT_ROLE = Qt.UserRole + 4
MASK = "\u2022" * 12


def display_name(item: vault.VaultItem) -> str:
    return item.title or item.website_or_app or "Untitled"


def item_brand(item: vault.VaultItem):
    return brands.resolve_brand(item.brand, item.website_or_app, item.title)


def website_url(text: str):
    """Return an http(s) URL for a website field, or None for app names / anything else."""
    text = text.strip()
    if not text or " " in text:
        return None
    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or "." not in parsed.netloc:
        return None
    return candidate


def format_time(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(iso).replace(tzinfo=datetime.timezone.utc).astimezone()
    except ValueError:
        return iso
    return dt.strftime("%d %b %Y, %H:%M")


class EntryDelegate(QStyledItemDelegate):
    """Paints each entry as a card row: avatar, title, username."""

    ROW_HEIGHT = 64

    def sizeHint(self, option, index):
        return QSize(0, self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 3, -4, -3)

        selected = option.state & QStyle.State_Selected
        hovered = option.state & QStyle.State_MouseOver
        if selected:
            painter.setPen(QColor(ACCENT))
            painter.setBrush(QColor(124, 92, 255, 46))
            painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        elif hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(SURFACE_2))
            painter.drawRoundedRect(rect, 12, 12)

        title = index.data(TITLE_ROLE) or ""
        subtitle = index.data(SUBTITLE_ROLE) or ""
        avatar = QRectF(rect.left() + 12, rect.center().y() - 19, 38, 38)
        draw_entry_icon(painter, avatar, title, brands.BRAND_BY_KEY.get(index.data(BRAND_ROLE)))

        text_left = avatar.right() + 14
        text_width = rect.right() - text_left - 10
        title_font = QFont(option.font)
        title_font.setPixelSize(14)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#ffffff"))
        fm = painter.fontMetrics()
        painter.drawText(QRectF(text_left, rect.top() + 11, text_width, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         fm.elidedText(title, Qt.ElideRight, int(text_width)))

        sub_font = QFont(option.font)
        sub_font.setPixelSize(12)
        painter.setFont(sub_font)
        painter.setPen(QColor(MUTED))
        fm = painter.fontMetrics()
        painter.drawText(QRectF(text_left, rect.top() + 32, text_width, 18), Qt.AlignLeft | Qt.AlignVCenter,
                         fm.elidedText(subtitle, Qt.ElideRight, int(text_width)))
        painter.restore()


class CategoryDelegate(QStyledItemDelegate):
    """Sidebar row: emoji tile, category name and an entry count."""

    ROW_HEIGHT = 44

    def sizeHint(self, option, index):
        return QSize(0, self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(option.rect).adjusted(2, 2, -2, -2)
        selected = option.state & QStyle.State_Selected
        if selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(124, 92, 255, 60))
            painter.drawRoundedRect(rect, 10, 10)
            painter.setBrush(QColor(ACCENT))
            painter.drawRoundedRect(QRectF(rect.left(), rect.top() + 10, 3, rect.height() - 20), 1.5, 1.5)
        elif option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(SURFACE_2))
            painter.drawRoundedRect(rect, 10, 10)

        symbol, color = index.data(BRAND_ROLE)
        tile = QRectF(rect.left() + 10, rect.center().y() - 14, 28, 28)
        draw_symbol_tile(painter, tile, symbol, color)

        count = index.data(COUNT_ROLE) or 0
        font = QFont(option.font)
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        count_text = str(count)
        badge_w = max(24, painter.fontMetrics().horizontalAdvance(count_text) + 14)
        badge = QRectF(rect.right() - badge_w - 8, rect.center().y() - 10, badge_w, 20)
        if count:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(ACCENT) if selected else QColor(SURFACE_2))
            painter.drawRoundedRect(badge, 10, 10)
        painter.setPen(QColor("#ffffff") if count else QColor(MUTED))
        painter.drawText(badge, Qt.AlignCenter, count_text)

        font.setPixelSize(13)
        font.setBold(bool(selected))
        painter.setFont(font)
        painter.setPen(QColor("#ffffff") if selected or count else QColor(MUTED))
        text_left = tile.right() + 12
        text_rect = QRectF(text_left, rect.top(), badge.left() - text_left - 6, rect.height())
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(index.data(TITLE_ROLE), Qt.ElideRight, int(text_rect.width())))
        painter.restore()


class FieldRow(QFrame):
    """Labelled value inside a rounded box with action buttons on the right."""

    def __init__(self, label: str, mono: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("FieldBox")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 10, 10)
        layout.setSpacing(8)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        caption = QLabel(label.upper())
        caption.setObjectName("FieldLabel")
        self.value = QLabel()
        self.value.setObjectName("Mono" if mono else "FieldValue")
        self.value.setTextFormat(Qt.PlainText)
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.value.setWordWrap(True)
        text_col.addWidget(caption)
        text_col.addWidget(self.value)
        layout.addLayout(text_col, 1)
        self._buttons = layout

    def add_button(self, text: str, slot, checkable: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("Small")
        btn.setCheckable(checkable)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(slot)
        self._buttons.addWidget(btn, 0, Qt.AlignVCenter)
        return btn


class MainWindow(QWidget):
    locked = Signal()
    auto_lock_changed = Signal(int)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setObjectName("VaultPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.session = session
        self._items: list[vault.VaultItem] = []
        self._current: vault.VaultItem = None
        self._selected_id = None  # survives searches that temporarily hide the entry
        self._category = None  # None = all categories
        self._build_ui()
        self._build_shortcuts()
        self.toast = Toast(self)
        self.reload_items()

    # ---------- layout ----------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(16)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_category_panel())
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_detail_area())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 0)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([230, 350, 800])
        body.addWidget(splitter)
        root.addLayout(body, 1)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(68)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(38))
        title = QLabel(f"Vaulti<span style='color:{BRAND_BLUE}'>x</span>")
        title.setObjectName("HeaderTitle")
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addStretch()

        chip = QFrame()
        chip.setObjectName("FieldBox")
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(6, 4, 14, 4)
        chip_layout.setSpacing(8)
        avatar = QLabel()
        avatar.setPixmap(avatar_pixmap(self.session.username, 26))
        name = QLabel(self.session.username)
        name.setTextFormat(Qt.PlainText)
        name.setStyleSheet("font-weight: 600;")
        chip_layout.addWidget(avatar)
        chip_layout.addWidget(name)
        layout.addWidget(chip, 0, Qt.AlignVCenter)
        layout.addSpacing(6)

        gen_btn = QPushButton("Generator")
        gen_btn.setObjectName("Secondary")
        gen_btn.setToolTip("Generate a strong password")
        gen_btn.clicked.connect(self._open_generator)
        layout.addWidget(gen_btn)

        self.settings_btn = QPushButton("Settings  \u25BE")
        self.settings_btn.setObjectName("Secondary")
        self.settings_btn.clicked.connect(self._open_settings_menu)
        layout.addWidget(self.settings_btn)

        lock_btn = QPushButton("Lock")
        lock_btn.setToolTip("Lock vault (Ctrl+L)")
        lock_btn.clicked.connect(self.locked.emit)
        layout.addWidget(lock_btn)
        return header

    def _build_category_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(200)
        panel.setMaximumWidth(280)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 16, 10, 10)
        layout.setSpacing(8)
        caption = QLabel("CATEGORIES")
        caption.setObjectName("FieldLabel")
        caption.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(caption)

        self.category_list = QListWidget()
        self.category_list.setItemDelegate(CategoryDelegate(self.category_list))
        self.category_list.setMouseTracking(True)
        self.category_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.category_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        rows = [(None, "All Items", brands.ALL_SYMBOL, ACCENT)]
        rows += [(c.key, c.label, c.symbol, c.color) for c in brands.CATEGORIES]
        for key, label, symbol, color in rows:
            entry = QListWidgetItem()
            entry.setData(ITEM_ID_ROLE, key)
            entry.setData(TITLE_ROLE, label)
            entry.setData(BRAND_ROLE, (symbol, color))
            self.category_list.addItem(entry)
        self.category_list.setCurrentRow(0)
        self.category_list.currentItemChanged.connect(self._on_category_changed)
        layout.addWidget(self.category_list, 1)
        return panel

    def _on_category_changed(self, current, _previous):
        self._category = current.data(ITEM_ID_ROLE) if current else None
        if self._category is not None and self.search_edit.text():
            self.search_edit.blockSignals(True)
            self.search_edit.clear()
            self.search_edit.blockSignals(False)
        self._apply_filter()

    def _select_category_row(self, key):
        for row in range(self.category_list.count()):
            if self.category_list.item(row).data(ITEM_ID_ROLE) == key:
                self.category_list.blockSignals(True)
                self.category_list.setCurrentRow(row)
                self.category_list.blockSignals(False)
                self._category = key
                return

    def _update_category_counts(self):
        counts = {}
        for it in self._items:
            counts[it.category] = counts.get(it.category, 0) + 1
        for row in range(self.category_list.count()):
            entry = self.category_list.item(row)
            key = entry.data(ITEM_ID_ROLE)
            entry.setData(COUNT_ROLE, len(self._items) if key is None else counts.get(key, 0))

    def _build_list_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(520)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("Search")
        self.search_edit.setPlaceholderText("Search vault...   Ctrl+F")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        add_btn = QPushButton("+ New")
        add_btn.setToolTip("Add entry (Ctrl+N)")
        add_btn.clicked.connect(self._add_entry)
        top.addWidget(self.search_edit, 1)
        top.addWidget(add_btn)
        layout.addLayout(top)

        self.count_label = QLabel()
        self.count_label.setObjectName("FieldLabel")
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setItemDelegate(EntryDelegate(self.list_widget))
        self.list_widget.setMouseTracking(True)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._edit_current())
        layout.addWidget(self.list_widget, 1)

        self.list_empty = QLabel()
        self.list_empty.setObjectName("Muted")
        self.list_empty.setTextFormat(Qt.PlainText)
        self.list_empty.setAlignment(Qt.AlignCenter)
        self.list_empty.setWordWrap(True)
        layout.addWidget(self.list_empty, 1)
        return panel

    def _build_detail_area(self) -> QStackedWidget:
        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(self._build_empty_state())
        self.detail_stack.addWidget(self._build_detail_card())
        return self.detail_stack

    def _build_empty_state(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(110, glow=True))
        logo.setAlignment(Qt.AlignCenter)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("DetailTitle")
        self.empty_title.setTextFormat(Qt.PlainText)
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_sub = QLabel()
        self.empty_sub.setObjectName("Subtitle")
        self.empty_sub.setAlignment(Qt.AlignCenter)
        self.empty_sub.setWordWrap(True)
        self.empty_btn = QPushButton("+ Add your first password")
        self.empty_btn.setMinimumHeight(42)
        self.empty_btn.clicked.connect(self._add_entry)
        layout.addWidget(logo)
        layout.addSpacing(6)
        layout.addWidget(self.empty_title)
        layout.addWidget(self.empty_sub)
        layout.addSpacing(8)
        layout.addWidget(self.empty_btn, 0, Qt.AlignCenter)
        return panel

    def _build_detail_card(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        outer = QVBoxLayout(panel)
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
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(16)
        self.detail_avatar = QLabel()
        top.addWidget(self.detail_avatar, 0, Qt.AlignTop)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.detail_title = QLabel()
        self.detail_title.setObjectName("DetailTitle")
        self.detail_title.setTextFormat(Qt.PlainText)
        self.detail_title.setWordWrap(True)
        self.detail_site = QLabel()
        self.detail_site.setObjectName("Subtitle")
        self.detail_site.setTextFormat(Qt.PlainText)
        title_col.addWidget(self.detail_title)
        title_col.addWidget(self.detail_site)
        top.addLayout(title_col, 1)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("Secondary")
        edit_btn.clicked.connect(self._edit_current)
        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("Danger")
        delete_btn.clicked.connect(self._delete_current)
        top.addWidget(edit_btn, 0, Qt.AlignTop)
        top.addWidget(delete_btn, 0, Qt.AlignTop)
        layout.addLayout(top)
        layout.addSpacing(10)

        self.username_row = FieldRow("Username / Email")
        self.username_row.add_button("Copy", lambda: self._copy("username"))
        layout.addWidget(self.username_row)

        self.password_row = FieldRow("Password", mono=True)
        self.reveal_btn = self.password_row.add_button("Show", self._toggle_reveal, checkable=True)
        self.password_row.add_button("Copy", lambda: self._copy("password"))
        layout.addWidget(self.password_row)
        self.detail_meter = StrengthMeter()
        meter_wrap = QHBoxLayout()
        meter_wrap.setContentsMargins(4, 0, 4, 0)
        meter_wrap.addWidget(self.detail_meter)
        layout.addLayout(meter_wrap)

        self.site_row = FieldRow("Website / App")
        self.open_btn = self.site_row.add_button("Open", self._open_website)
        layout.addWidget(self.site_row)

        self.notes_row = FieldRow("Notes")
        layout.addWidget(self.notes_row)

        layout.addStretch()
        self.detail_footer = QLabel()
        self.detail_footer.setObjectName("Muted")
        layout.addWidget(self.detail_footer)
        return panel

    def _build_shortcuts(self):
        QShortcut(QKeySequence.New, self, self._add_entry)
        QShortcut(QKeySequence.Find, self, self._focus_search)
        QShortcut(QKeySequence("Ctrl+L"), self, self.locked.emit)
        QShortcut(QKeySequence("Ctrl+G"), self, self._open_generator)
        delete = QShortcut(QKeySequence.Delete, self.list_widget, self._delete_current)
        delete.setContext(Qt.WidgetShortcut)
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self.search_edit, self.search_edit.clear)
        esc.setContext(Qt.WidgetShortcut)

    def _on_search_changed(self, text: str):
        # Searching always looks through every category.
        if text.strip() and self._category is not None:
            self._select_category_row(None)
        self._apply_filter()

    def _focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    # ---------- data ----------

    def reload_items(self, select_id: int = None):
        if self.session is None:
            return
        self._items = sorted(vault.list_items(self.session), key=lambda it: display_name(it).lower())
        self._update_category_counts()
        self._apply_filter(select_id=select_id)

    def _apply_filter(self, *_, select_id: int = None):
        if select_id is None:
            select_id = self._selected_id
        query = self.search_edit.text()
        shown = vault.filter_items(self._items, query, self._category)

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        select_row = -1
        for row, it in enumerate(shown):
            entry = QListWidgetItem()
            entry.setData(ITEM_ID_ROLE, it.id)
            entry.setData(TITLE_ROLE, display_name(it))
            entry.setData(SUBTITLE_ROLE, it.username or it.website_or_app or "No username")
            brand = item_brand(it)
            entry.setData(BRAND_ROLE, brand.key if brand else "")
            self.list_widget.addItem(entry)
            if it.id == select_id:
                select_row = row
        self.list_widget.blockSignals(False)

        n = len(shown)
        noun = f"ENTR{'Y' if n == 1 else 'IES'}"
        if query.strip():
            self.count_label.setText(f"{n} OF {len(self._items)} ENTRIES")
        elif self._category is not None:
            self.count_label.setText(f"{brands.CATEGORY_BY_KEY[self._category].label.upper()}  \u00B7  {n} {noun}")
        else:
            self.count_label.setText(f"ALL ITEMS  \u00B7  {n} {noun}")

        has_rows = bool(shown)
        self.list_widget.setVisible(has_rows)
        self.list_empty.setVisible(not has_rows)
        if not has_rows:
            if query.strip():
                self.list_empty.setText(f"No entries match \u201c{query.strip()}\u201d.")
            elif self._category is not None:
                self.list_empty.setText(f"No {brands.CATEGORY_BY_KEY[self._category].label} entries yet.\n"
                                        "Click + New to add one.")
            else:
                self.list_empty.setText("Nothing here yet.\nClick + New to add an entry.")

        if select_row < 0 and has_rows:
            select_row = 0
        if select_row >= 0:
            self.list_widget.setCurrentRow(select_row)
            self._show_item(self._find(shown[select_row].id))
        else:
            self.list_widget.setCurrentRow(-1)
            self._show_item(None)

    def _find(self, item_id):
        return next((it for it in self._items if it.id == item_id), None)

    def _on_current_changed(self, current, _previous):
        self._show_item(self._find(current.data(ITEM_ID_ROLE)) if current else None)

    def _show_item(self, item):
        previous = self._current
        self._current = item
        if item is not None:
            self._selected_id = item.id
        if item is None:
            if self.search_edit.text().strip():
                self.empty_title.setText("No matching entries")
                self.empty_sub.setText("Try a different search, or add a new entry.")
                self.empty_btn.setText("+ Add entry")
            elif self._category is not None:
                cat = brands.CATEGORY_BY_KEY[self._category]
                self.empty_title.setText(f"No {cat.label} yet")
                self.empty_sub.setText("Add an account and pick its logo from the list.")
                self.empty_btn.setText(f"+ Add to {cat.label}")
            else:
                self.empty_title.setText("Your vault is empty")
                self.empty_sub.setText("Save your first password: your bank, email, Netflix, anything.\n"
                                       "Only you can open it.")
                self.empty_btn.setText("+ Add your first password")
            self.detail_stack.setCurrentIndex(0)
            return

        self.detail_avatar.setPixmap(entry_icon_pixmap(display_name(item), item_brand(item), 64))
        self.detail_title.setText(display_name(item))
        cat = brands.CATEGORY_BY_KEY[item.category]
        site = item.website_or_app if item.title else ""
        self.detail_site.setText(cat.label + (f"   \u00B7   {site}" if site else ""))
        self.username_row.value.setText(item.username or "\u2014")
        self.reveal_btn.setChecked(False)
        self._render_password()
        self.detail_meter.update_for(item.password, [item.username, item.title])
        self.site_row.setVisible(bool(item.website_or_app))
        self.site_row.value.setText(item.website_or_app)
        self.open_btn.setVisible(website_url(item.website_or_app) is not None)
        self.notes_row.setVisible(bool(item.notes))
        self.notes_row.value.setText(item.notes)
        footer = []
        if item.created_at:
            footer.append(f"Created {format_time(item.created_at)}")
        if item.updated_at and item.updated_at != item.created_at:
            footer.append(f"Updated {format_time(item.updated_at)}")
        self.detail_footer.setText("   \u00B7   ".join(footer))

        was_hidden = self.detail_stack.currentIndex() != 1
        self.detail_stack.setCurrentIndex(1)
        if was_hidden or previous is None or previous.id != item.id:
            fade_in(self.detail_stack.currentWidget(), 160)

    def _render_password(self):
        if self._current is None:
            return
        shown = self.reveal_btn.isChecked()
        self.password_row.value.setText(self._current.password if shown else MASK)
        self.reveal_btn.setText("Hide" if shown else "Show")

    def _toggle_reveal(self):
        self._render_password()

    # ---------- actions ----------

    def _copy(self, field: str):
        if self._current is None:
            return
        value = getattr(self._current, field)
        if not value:
            self.toast.show_message(f"This entry has no {field}.")
            return
        shared_clipboard_guard().copy(value)
        self.toast.show_message(f"{field.capitalize()} copied  \u00B7  clipboard clears in 25s")

    def _open_website(self):
        if self._current is None:
            return
        url = website_url(self._current.website_or_app)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _add_entry(self):
        if self.session is None:
            return
        dlg = ItemEditorDialog(self, category=self._category)
        if dlg.exec() != QDialog.Accepted or self.session is None:
            return
        new_item = dlg.get_item()
        new_id = vault.add_item(self.session, new_item)
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        if self._category not in (None, new_item.category):
            self._select_category_row(new_item.category)
        self.reload_items(select_id=new_id)
        self.toast.show_message("Entry saved")

    def _edit_current(self):
        item = self._current
        if item is None or self.session is None:
            return
        dlg = ItemEditorDialog(self, item=item)
        if dlg.exec() != QDialog.Accepted or self.session is None:
            return
        updated = dlg.get_item()
        vault.update_item(self.session, updated)
        if self._category not in (None, updated.category):
            self._select_category_row(updated.category)
        self.reload_items(select_id=item.id)
        self.toast.show_message("Changes saved")

    def _delete_current(self):
        item = self._current
        if item is None or self.session is None:
            return
        box = QMessageBox(QMessageBox.Question, "Delete entry",
                          f"Delete \u201c{display_name(item)}\u201d permanently?\nThis cannot be undone.",
                          QMessageBox.Yes | QMessageBox.No, self)
        box.setTextFormat(Qt.PlainText)
        box.setDefaultButton(QMessageBox.No)
        resp = box.exec()
        if resp != QMessageBox.Yes or self.session is None:
            return
        row = self.list_widget.currentRow()
        vault.delete_item(self.session, item.id)
        self._current = None
        self._selected_id = None
        self.reload_items()
        if self.list_widget.count():
            self.list_widget.setCurrentRow(min(row, self.list_widget.count() - 1))
        self.toast.show_message("Entry deleted")

    def _open_generator(self):
        if self.session is None:
            return
        PasswordGeneratorDialog(self, user_inputs=[self.session.username]).exec()

    # ---------- settings ----------

    def _open_settings_menu(self):
        if self.session is None:
            return
        totp_on = self._totp_enabled()
        menu = QMenu(self)
        menu.addAction("Change Master Password...", self._change_password)
        if totp_on:
            menu.addAction("Turn Off 2-Step Login...", self._disable_2fa)
        else:
            menu.addAction("Turn On 2-Step Login...", self._enable_2fa)
        menu.addAction("New Backup Key...", self._regenerate_recovery)
        menu.addAction("Auto-Lock Timer...", self._configure_auto_lock)
        menu.addSeparator()
        menu.addAction("Password Generator", self._open_generator)
        menu.addAction("About Vaultix", lambda: AboutDialog(self).exec())
        menu.addAction("Lock Vault", self.locked.emit)

        # Drop the menu just under the button, right edges aligned.
        btn = self.settings_btn
        hint = menu.sizeHint()
        menu.exec(btn.mapToGlobal(QPoint(btn.width() - hint.width(), btn.height() + 6)))

    def _totp_enabled(self) -> bool:
        user = db.get_user_by_id(self.session.user_id)
        return bool(user and user["totp_enabled"])

    def _change_password(self):
        if ChangePasswordDialog(self.session, self).exec() == QDialog.Accepted:
            self.toast.show_message("Master password changed")

    def _enable_2fa(self):
        if TwoFactorSetupDialog(self.session, self).exec() == QDialog.Accepted:
            self.toast.show_message("2-step login is on")

    def _disable_2fa(self):
        if not ConfirmPasswordDialog.confirm(
                self.session, "Enter your master password to turn off 2-step login.", self):
            return
        if self.session is None:
            return
        totp_mod.disable_2fa(self.session)
        self.toast.show_message("2-step login is off")

    def _regenerate_recovery(self):
        resp = QMessageBox.question(
            self, "New Backup Key",
            "This creates a new backup key. Your old key and old backup files will stop working.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        if not ConfirmPasswordDialog.confirm(self.session, "Enter your master password to create a new backup key.", self):
            return
        session = self.session
        if session is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        run_in_background(lambda: recovery_mod.regenerate_recovery_key(session),
                          self._recovery_regenerated, self._recovery_failed)

    def _recovery_regenerated(self, new_key: str):
        QApplication.restoreOverrideCursor()
        if self.session is None:
            return
        RecoveryKeyDialog(new_key, self.session.username, self).exec()

    def _recovery_failed(self, error):
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(self, "Error", f"Could not create a new backup key:\n{error}")

    def _configure_auto_lock(self):
        user = db.get_user_by_id(self.session.user_id)
        dlg = AutoLockDialog(user["auto_lock_minutes"] if user else 5, self)
        if dlg.exec() != QDialog.Accepted or self.session is None:
            return
        minutes = dlg.minutes()
        db.set_auto_lock_minutes(self.session.user_id, minutes)
        self.auto_lock_changed.emit(minutes)
        self.toast.show_message(f"Vault will auto-lock after {minutes} min of inactivity")

    # ---------- lock ----------

    def wipe(self):
        """Drop every decrypted value and the session key from this window."""
        self.session = None
        self._items = []
        self._current = None
        self._selected_id = None
        self.list_widget.clear()
        for row in (self.username_row, self.password_row, self.site_row, self.notes_row):
            row.value.clear()
        self.detail_title.clear()
        self.detail_site.clear()
        self.detail_avatar.clear()
        self.detail_footer.clear()
        self.search_edit.clear()
        self._update_category_counts()
        self.detail_stack.setCurrentIndex(0)
