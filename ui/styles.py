"""Centralized Qt stylesheet for a clean, modern dark UI."""

APP_STYLE = """
QWidget {
    background-color: #1e1f29;
    color: #e6e6e6;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1e1f29;
}

QLabel#TitleLabel {
    font-size: 22px;
    font-weight: 600;
    color: #ffffff;
}

QLabel#SubtitleLabel {
    font-size: 12px;
    color: #9a9ab0;
}

QLineEdit, QTextEdit, QComboBox, QSpinBox {
    background-color: #2a2b38;
    border: 1px solid #3c3d4d;
    border-radius: 6px;
    padding: 8px 10px;
    color: #ffffff;
    selection-background-color: #6c5ce7;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #6c5ce7;
}

QPushButton {
    background-color: #6c5ce7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 9px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #7d6ff0;
}

QPushButton:pressed {
    background-color: #5a4bd4;
}

QPushButton#SecondaryButton {
    background-color: #2a2b38;
    color: #e6e6e6;
    border: 1px solid #3c3d4d;
}

QPushButton#SecondaryButton:hover {
    background-color: #343547;
}

QPushButton#DangerButton {
    background-color: #e74c3c;
}

QPushButton#DangerButton:hover {
    background-color: #ec6a5c;
}

QListWidget, QTableWidget {
    background-color: #24252f;
    border: 1px solid #3c3d4d;
    border-radius: 8px;
    outline: none;
}

QListWidget::item, QTableWidget::item {
    padding: 10px;
    border-bottom: 1px solid #2e2f3b;
}

QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #6c5ce7;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #2a2b38;
    color: #9a9ab0;
    border: none;
    padding: 8px;
    font-weight: 600;
}

QScrollBar:vertical {
    background: #1e1f29;
    width: 10px;
}

QScrollBar::handle:vertical {
    background: #3c3d4d;
    border-radius: 5px;
    min-height: 20px;
}

QProgressBar {
    border: 1px solid #3c3d4d;
    border-radius: 6px;
    background-color: #2a2b38;
    text-align: center;
    color: #ffffff;
}

QProgressBar::chunk {
    border-radius: 6px;
}

QTabWidget::pane {
    border: 1px solid #3c3d4d;
    border-radius: 8px;
}

QTabBar::tab {
    background: #2a2b38;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #9a9ab0;
}

QTabBar::tab:selected {
    background: #6c5ce7;
    color: #ffffff;
}

QCheckBox {
    spacing: 8px;
}
"""

STRENGTH_COLORS = {
    0: "#e74c3c",  # very weak
    1: "#e67e22",  # weak
    2: "#f1c40f",  # fair
    3: "#2ecc71",  # good
    4: "#27ae60",  # strong
}
