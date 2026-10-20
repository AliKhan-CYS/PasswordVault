"""Centralized Qt stylesheet: deep-navy dark theme with violet/cyan accents."""

BG = "#0e1022"
SURFACE = "#171a33"
SURFACE_2 = "#1f2342"
BORDER = "#2b3058"
TEXT = "#e9ebf8"
MUTED = "#8a90b8"
ACCENT = "#7c5cff"
ACCENT_2 = "#22d3ee"
BRAND_BLUE = "#2f8cff"
SUCCESS = "#22c55e"
DANGER = "#ef4444"

APP_STYLE = f"""
QWidget {{
    color: {TEXT};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}

QDialog, QMessageBox {{
    background-color: {SURFACE};
}}

QWidget#AppRoot, QWidget#VaultPage {{
    background-color: {BG};
}}

QWidget#AuthPage {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0b0d1f, stop:0.55 #1a1145, stop:1 #062a3a);
}}

QLabel, QCheckBox, QRadioButton {{
    background: transparent;
}}

QFrame#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 18px;
}}

QFrame#Panel {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

QFrame#Header {{
    background-color: {SURFACE};
    border-bottom: 1px solid {BORDER};
}}

QFrame#FieldBox {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLabel#Title {{
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
}}

QLabel#HeaderTitle {{
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}}

QLabel#DetailTitle {{
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
}}

QLabel#DialogTitle {{
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}}

QLabel#Subtitle, QLabel#Muted {{
    color: {MUTED};
}}

QLabel#FieldLabel {{
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QLabel#FieldValue {{
    font-size: 15px;
    color: #ffffff;
}}

QLabel#Mono {{
    font-family: 'Cascadia Mono', 'Consolas', monospace;
    font-size: 15px;
    color: #ffffff;
}}

QLabel#Error {{
    color: #ff8a8a;
    background-color: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 8px;
    padding: 8px 10px;
}}

QLabel#Warning {{
    color: #fcd34d;
    background-color: rgba(245, 158, 11, 0.10);
    border: 1px solid rgba(245, 158, 11, 0.35);
    border-radius: 8px;
    padding: 10px 12px;
}}

QLabel#Chip {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 5px 12px;
    color: {TEXT};
}}

QLabel#Toast {{
    background-color: #262b52;
    color: #ffffff;
    border: 1px solid {ACCENT};
    border-radius: 12px;
    padding: 11px 20px;
    font-weight: 600;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
    background-color: #12142b;
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 12px;
    color: #ffffff;
    selection-background-color: {ACCENT};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
    background-color: #15183a;
}}

QLineEdit[error="true"] {{
    border: 1px solid {DANGER};
}}

QLineEdit#Search {{
    padding-left: 14px;
    border-radius: 12px;
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    outline: none;
    padding: 4px;
}}

QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6366f1);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 18px;
    font-weight: 600;
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #818cf8);
}}

QPushButton:pressed {{
    background: #5b3fd6;
}}

QPushButton:disabled {{
    background: #2a2e52;
    color: #6f7499;
}}

QPushButton#Secondary {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
}}

QPushButton#Secondary:hover {{
    background: #2a2f58;
    border: 1px solid #3b4178;
}}

QPushButton#Secondary:checked {{
    background: #2a2f58;
    border: 1px solid {ACCENT};
}}

QPushButton#Danger {{
    background: rgba(239, 68, 68, 0.12);
    color: #ff8a8a;
    border: 1px solid rgba(239, 68, 68, 0.45);
}}

QPushButton#Danger:hover {{
    background: {DANGER};
    color: #ffffff;
}}

QPushButton#Ghost {{
    background: transparent;
    color: {MUTED};
    border: none;
    padding: 6px 10px;
}}

QPushButton#Ghost:hover {{
    color: #ffffff;
    background: rgba(124, 92, 255, 0.15);
}}

QPushButton#Small {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
}}

QPushButton#Small:hover {{
    border: 1px solid {ACCENT};
    color: #ffffff;
}}

QPushButton#Small:checked {{
    border: 1px solid {ACCENT};
    background: rgba(124, 92, 255, 0.18);
}}

QListView, QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}

QTabWidget::pane {{
    border: none;
    background: transparent;
}}

QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 10px 6px;
    margin-right: 4px;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}}

QTabBar::tab:hover {{
    color: #ffffff;
}}

QTabBar::tab:selected {{
    color: #ffffff;
    border-bottom: 2px solid {ACCENT};
}}

QMenu {{
    background-color: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px;
}}

QMenu::item {{
    padding: 9px 22px 9px 14px;
    border-radius: 8px;
    color: {TEXT};
}}

QMenu::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 8px;
}}

QProgressBar {{
    border: none;
    border-radius: 3px;
    background-color: #262a4d;
    max-height: 6px;
    min-height: 6px;
}}

QProgressBar::chunk {{
    border-radius: 3px;
}}

QSlider::groove:horizontal {{
    height: 6px;
    background: #262a4d;
    border-radius: 3px;
}}

QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #22d3ee);
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background: #ffffff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QCheckBox {{
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #3b4178;
    background: #12142b;
}}

QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
}}

QSplitter::handle {{
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}}

QScrollBar::handle:vertical {{
    background: #2f3460;
    border-radius: 3px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #3f4580;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
}}

QToolTip {{
    background-color: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 8px;
    border-radius: 6px;
}}
"""

STRENGTH_COLORS = {
    0: "#ef4444",
    1: "#f97316",
    2: "#eab308",
    3: "#22c55e",
    4: "#10b981",
}

AVATAR_COLORS = [
    "#7c3aed", "#2563eb", "#0891b2", "#059669",
    "#d97706", "#db2777", "#dc2626", "#4f46e5",
]
