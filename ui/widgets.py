"""Reusable widgets and UI helpers."""

import zlib

from PySide6.QtCore import (
    Qt, QObject, QRunnable, QThreadPool, Signal, Slot, QTimer, QRectF, QPointF,
    QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QPoint,
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QPen, QFont, QIcon, QImage, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLineEdit, QPushButton, QLabel,
    QProgressBar, QGraphicsOpacityEffect, QApplication,
)

from app import vault, auth
from ui.styles import STRENGTH_COLORS, AVATAR_COLORS, SUCCESS, MUTED


# ---------- background work ----------

_jobs = set()


class _Job(QObject):
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, on_success, on_error):
        super().__init__()
        self._on_success = on_success
        self._on_error = on_error
        self.succeeded.connect(self._handle_success)
        self.failed.connect(self._handle_error)

    @Slot(object)
    def _handle_success(self, result):
        _jobs.discard(self)
        self._on_success(result)

    @Slot(object)
    def _handle_error(self, error):
        _jobs.discard(self)
        self._on_error(error)


class _Runnable(QRunnable):
    def __init__(self, fn, job):
        super().__init__()
        self._fn = fn
        self._job = job

    def run(self):
        try:
            result = self._fn()
        except Exception as e:  # delivered to the UI thread via the job's signal
            self._job.failed.emit(e)
            return
        self._job.succeeded.emit(result)


def run_in_background(fn, on_success, on_error):
    """Run fn() on a worker thread (Argon2 takes ~0.5s); callbacks run on the UI thread."""
    job = _Job(on_success, on_error)
    _jobs.add(job)
    QThreadPool.globalInstance().start(_Runnable(fn, job))


def set_busy(button: QPushButton, busy: bool, busy_text: str = "Please wait..."):
    if busy:
        button.setProperty("idle_text", button.text())
        button.setText(busy_text)
        button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
    else:
        button.setText(button.property("idle_text") or button.text())
        button.setEnabled(True)
        QApplication.restoreOverrideCursor()


# ---------- painting ----------

def logo_pixmap(size: int) -> QPixmap:
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    s = size * ratio
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    grad = QLinearGradient(0, 0, s, s)
    grad.setColorAt(0, QColor("#8b5cf6"))
    grad.setColorAt(1, QColor("#06b6d4"))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.28, s * 0.28)

    pen = QPen(QColor("white"), s * 0.075)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    sw, sy = s * 0.32, s * 0.19
    sx = (s - sw) / 2
    p.drawArc(QRectF(sx, sy, sw, sw), 0, 180 * 16)
    p.drawLine(QPointF(sx, sy + sw / 2), QPointF(sx, s * 0.47))
    p.drawLine(QPointF(sx + sw, sy + sw / 2), QPointF(sx + sw, s * 0.47))

    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    bw, bh = s * 0.52, s * 0.37
    bx, by = (s - bw) / 2, s * 0.44
    p.drawRoundedRect(QRectF(bx, by, bw, bh), s * 0.07, s * 0.07)

    p.setBrush(QColor("#6d28d9"))
    kr = s * 0.055
    cx, cy = s / 2, by + bh * 0.40
    p.drawEllipse(QPointF(cx, cy), kr, kr)
    p.drawRoundedRect(QRectF(cx - kr * 0.45, cy, kr * 0.9, bh * 0.32), kr * 0.3, kr * 0.3)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def app_icon() -> QIcon:
    return QIcon(logo_pixmap(128))


def avatar_color(text: str) -> QColor:
    return QColor(AVATAR_COLORS[zlib.crc32(text.lower().encode("utf-8")) % len(AVATAR_COLORS)])


def avatar_initial(text: str) -> str:
    text = text.strip()
    return text[0].upper() if text else "?"


def draw_avatar(painter: QPainter, rect: QRectF, text: str, radius_ratio: float = 0.3):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    base = avatar_color(text)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, base.lighter(125))
    grad.setColorAt(1, base.darker(115))
    painter.setPen(Qt.NoPen)
    painter.setBrush(grad)
    painter.drawRoundedRect(rect, rect.width() * radius_ratio, rect.height() * radius_ratio)
    font = QFont(painter.font())
    font.setBold(True)
    font.setPixelSize(int(rect.height() * 0.45))
    painter.setFont(font)
    painter.setPen(QColor("white"))
    painter.drawText(rect, Qt.AlignCenter, avatar_initial(text))
    painter.restore()


def avatar_pixmap(text: str, size: int) -> QPixmap:
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_avatar(p, QRectF(0, 0, size * ratio, size * ratio), text)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


# ---------- brand logos & category icons ----------

_logo_cache: dict[str, QImage] = {}


def brand_logo(brand) -> QImage:
    if brand is None:
        return None
    if brand.key not in _logo_cache:
        path = brand.logo_path
        img = QImage(path) if path else QImage()
        _logo_cache[brand.key] = None if img.isNull() else img
    return _logo_cache[brand.key]


def draw_entry_icon(painter: QPainter, rect: QRectF, title: str, brand=None):
    """Brand logo on a rounded tile, or a coloured initial when the service is unknown."""
    logo = brand_logo(brand)
    if logo is None:
        draw_avatar(painter, rect, title)
        return
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    radius = rect.width() * 0.26
    path.addRoundedRect(rect, radius, radius)
    painter.setClipPath(path)
    painter.fillRect(rect, QColor("#2a2e52"))
    painter.drawImage(rect, logo)
    painter.restore()


def entry_icon_pixmap(title: str, brand, size: int) -> QPixmap:
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_entry_icon(p, QRectF(0, 0, size * ratio, size * ratio), title, brand)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def draw_symbol_tile(painter: QPainter, rect: QRectF, symbol: str, color: str):
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    tint = QColor(color)
    tint.setAlpha(60)
    painter.setPen(Qt.NoPen)
    painter.setBrush(tint)
    painter.drawRoundedRect(rect, rect.width() * 0.3, rect.height() * 0.3)
    font = QFont("Segoe UI Emoji")
    font.setPixelSize(int(rect.height() * 0.52))
    painter.setFont(font)
    painter.setPen(QColor("white"))
    painter.drawText(rect, Qt.AlignCenter, symbol)
    painter.restore()


def symbol_icon(symbol: str, color: str, size: int = 24) -> QIcon:
    ratio = 2
    pm = QPixmap(size * ratio, size * ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_symbol_tile(p, QRectF(0, 0, size * ratio, size * ratio), symbol, color)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return QIcon(pm)


def brand_icon(brand, size: int = 24) -> QIcon:
    return QIcon(entry_icon_pixmap(brand.name, brand, size))


# ---------- inputs ----------

class PasswordField(QWidget):
    """Password line edit with a Show/Hide toggle."""

    def __init__(self, placeholder: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText(placeholder)
        self.toggle = QPushButton("Show")
        self.toggle.setObjectName("Small")
        self.toggle.setCheckable(True)
        self.toggle.setFocusPolicy(Qt.NoFocus)
        self.toggle.setFixedWidth(64)
        self.toggle.toggled.connect(self._on_toggle)
        layout.addWidget(self.edit)
        layout.addWidget(self.toggle)

    def _on_toggle(self, shown: bool):
        self.edit.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password)
        self.toggle.setText("Hide" if shown else "Show")

    def text(self) -> str:
        return self.edit.text()

    def setText(self, text: str):
        self.edit.setText(text)

    def clear(self):
        self.edit.clear()
        self.toggle.setChecked(False)


def set_error(edit: QLineEdit, error: bool):
    edit.setProperty("error", "true" if error else "false")
    edit.style().unpolish(edit)
    edit.style().polish(edit)


class StrengthMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.bar = QProgressBar()
        self.bar.setRange(0, 5)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.label = QLabel()
        self.label.setObjectName("Muted")
        layout.addWidget(self.bar)
        layout.addWidget(self.label)

    def update_for(self, password: str, user_inputs=None):
        info = vault.password_strength(password, user_inputs)
        if not password:
            self.bar.setValue(0)
            self.label.setText("")
            return info
        score = info["score"]
        self.bar.setValue(score + 1)
        color = STRENGTH_COLORS[score]
        self.bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}")
        self.label.setText(
            f"<span style='color:{color}; font-weight:600'>{info['label']}</span>"
            f"<span style='color:{MUTED}'>  ·  cracks in {info['crack_time_display']}</span>"
        )
        return info


class RuleChecklist(QWidget):
    """Live checklist of master-password rules (plus optional 'passwords match')."""

    changed = Signal(bool)

    def __init__(self, username_source, password_edit: QLineEdit, confirm_edit: QLineEdit = None, parent=None):
        super().__init__(parent)
        self._username_source = username_source
        self._password_edit = password_edit
        self._confirm_edit = confirm_edit
        layout = QGridLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(3)
        labels = [label for label, _ in auth.PASSWORD_RULES]
        if confirm_edit is not None:
            labels.append("Passwords match")
        self._labels = []
        for i, text in enumerate(labels):
            lbl = QLabel()
            # Short rules pair up in two columns; longer ones take a full row.
            if i < 4:
                layout.addWidget(lbl, i // 2, i % 2)
            else:
                layout.addWidget(lbl, i - 2, 0, 1, 2)
            self._labels.append(lbl)
        password_edit.textChanged.connect(self.refresh)
        if confirm_edit is not None:
            confirm_edit.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        password = self._password_edit.text()
        results = auth.password_rule_results(self._username_source(), password)
        if self._confirm_edit is not None:
            results.append(("Passwords match", bool(password) and password == self._confirm_edit.text()))
        for lbl, (text, ok) in zip(self._labels, results):
            mark, color = ("✓", SUCCESS) if ok else ("○", MUTED)
            lbl.setText(f"<span style='color:{color}'>{mark}&nbsp;&nbsp;{text}</span>")
        valid = all(ok for _, ok in results)
        self.changed.emit(valid)
        return valid

    def is_valid(self) -> bool:
        return self.refresh()


# ---------- feedback ----------

class Toast(QLabel):
    """Non-blocking notification that fades in at the bottom of its parent."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)
        self._anim.finished.connect(self._on_anim_finished)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, msec: int = 2400):
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 36)
        self.raise_()
        self.show()
        self._animate_to(1.0)
        self._hide_timer.start(msec)

    def _fade_out(self):
        self._animate_to(0.0)

    def _animate_to(self, value: float):
        self._anim.stop()
        self._anim.setStartValue(self._effect.opacity())
        self._anim.setEndValue(value)
        self._anim.start()

    def _on_anim_finished(self):
        if self._effect.opacity() <= 0.01:
            self.hide()


def shake(widget: QWidget):
    origin = widget.pos()
    group = QSequentialAnimationGroup(widget)
    for dx in (10, -9, 7, -5, 3, 0):
        anim = QPropertyAnimation(widget, b"pos")
        anim.setDuration(45)
        anim.setEndValue(origin + QPoint(dx, 0))
        group.addAnimation(anim)
    group.start(QSequentialAnimationGroup.DeleteWhenStopped)


def fade_in(widget: QWidget, duration: int = 220):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    # Drop the effect afterwards so it doesn't cost anything on every repaint.
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start(QPropertyAnimation.DeleteWhenStopped)
