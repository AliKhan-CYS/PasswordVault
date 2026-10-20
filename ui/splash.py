"""Animated intro: the Vaultix shield, name, tagline and creator credit."""

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QRadialGradient, QFont, QPen
from PySide6.QtWidgets import QWidget

from app.branding import APP_NAME, CREATOR
from ui.styles import BRAND_BLUE as _BRAND_BLUE_HEX
from ui.widgets import brand_image

BRAND_BLUE = QColor(_BRAND_BLUE_HEX)

DURATION_MS = 3600
_OUT_BACK = QEasingCurve(QEasingCurve.OutBack)
_OUT_CUBIC = QEasingCurve(QEasingCurve.OutCubic)


def _phase(t: float, start: float, length: float, curve: QEasingCurve = _OUT_CUBIC) -> float:
    x = min(1.0, max(0.0, (t - start) / length))
    return curve.valueForProgress(x)


def _paint_background(p: QPainter, rect):
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, QColor("#0b0d1f"))
    grad.setColorAt(0.55, QColor("#1a1145"))
    grad.setColorAt(1, QColor("#062a3a"))
    p.fillRect(rect, grad)


class SplashScreen(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = 0.0
        self._done = False
        self.setFocusPolicy(Qt.StrongFocus)
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(float(DURATION_MS))
        self._anim.setDuration(DURATION_MS)
        self._anim.valueChanged.connect(self._tick)
        self._anim.finished.connect(self._finish)

    def start(self):
        self._anim.start()
        self.setFocus()

    def skip(self):
        self._anim.stop()
        self._finish()

    def _tick(self, value):
        self._t = value
        self.update()

    def _finish(self):
        if not self._done:
            self._done = True
            self.finished.emit()

    def mousePressEvent(self, event):
        self.skip()

    def keyPressEvent(self, event):
        self.skip()

    def paintEvent(self, event):
        t = self._t
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        _paint_background(p, self.rect())

        fade_out = 1.0 - _phase(t, DURATION_MS - 450, 450)
        p.setOpacity(fade_out)

        w, h = self.width(), self.height()
        logo_size = min(220.0, h * 0.32)
        cx, cy = w / 2, h * 0.40

        # Shockwave ring that expands out of the shield as it lands.
        ring = _phase(t, 450, 1100)
        if 0 < ring < 1:
            radius = logo_size * (0.45 + ring * 1.1)
            pen = QPen(QColor(47, 140, 255, int(150 * (1 - ring))), 2 + 4 * (1 - ring))
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), radius, radius)

        # Soft halo that breathes behind the shield.
        halo = _phase(t, 300, 900) * (0.75 + 0.25 * _phase(t, 1200, 900))
        if halo > 0:
            r = logo_size * 1.15
            glow = QRadialGradient(QPointF(cx, cy), r)
            glow.setColorAt(0, QColor(47, 140, 255, int(110 * halo)))
            glow.setColorAt(1, QColor(47, 140, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # Shield pops in.
        pop = _phase(t, 0, 900, _OUT_BACK)
        appear = _phase(t, 0, 500)
        if appear > 0:
            size = logo_size * (0.55 + 0.45 * pop)
            p.save()
            p.setOpacity(fade_out * appear)
            p.drawImage(QRectF(cx - size / 2, cy - size / 2, size, size), brand_image(glow=True))
            p.restore()

        # Name, tagline and credit rise in one after another.
        name_y = cy + logo_size * 0.62
        self._text_line(p, t, 850, name_y, self._name_parts(), 46, QFont.Black, letter_spacing=10, fade=fade_out)
        self._text_line(p, t, 1350, name_y + 92, [("Your secrets, ", "#e9ebf8"), ("your security", BRAND_BLUE.name())],
                        19, QFont.Normal, letter_spacing=3, fade=fade_out)

        credit = _phase(t, 1900, 600)
        if credit > 0:
            p.setOpacity(fade_out * credit)
            f = QFont("Segoe UI", 11)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 2)
            p.setFont(f)
            p.setPen(QColor("#8a90b8"))
            p.drawText(QRectF(0, h - 70, w, 30), Qt.AlignCenter, f"CREATED BY  {CREATOR.upper()}")
        p.end()

    @staticmethod
    def _name_parts():
        return [(APP_NAME[:-1].upper(), "#ffffff"), (APP_NAME[-1].upper(), BRAND_BLUE.name())]

    def _text_line(self, p: QPainter, t, start, y, parts, point_size, weight, letter_spacing, fade):
        k = _phase(t, start, 650)
        if k <= 0:
            return
        f = QFont("Segoe UI", point_size, weight)
        f.setLetterSpacing(QFont.AbsoluteSpacing, letter_spacing)
        p.setFont(f)
        fm = p.fontMetrics()
        total = sum(fm.horizontalAdvance(text) for text, _ in parts)
        x = (self.width() - total) / 2
        baseline = y + fm.ascent() + 18 * (1 - k)
        p.setOpacity(fade * k)
        for text, color in parts:
            p.setPen(QColor(color))
            p.drawText(QPointF(x, baseline), text)
            x += fm.horizontalAdvance(text)
        p.setOpacity(fade)
