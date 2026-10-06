"""Shared visual theme for SayIt.

Provides:
- ``sayit_mark()``: a simple, code-drawn vector mark (a microphone capsule with
  an audio-waveform motif) returned as a QPixmap/QIcon. No external image asset
  is used — the mark is painted so it scales cleanly for the tray, window
  header, and future icon use.
- ``STYLESHEET``: a calm, neutral Qt stylesheet with restrained spacing,
  typography, and subtle borders. It uses the palette's own colors where
  possible so it reads reasonably in both light and dark system themes.

This module is presentation-only. It does not change application behavior.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# Restrained accent used for interactive/recording emphasis. A quiet teal rather
# than a neon "AI" color.
BRAND_ORANGE = "#FF6600"
ACCENT = BRAND_ORANGE
ACCENT_RECORDING = BRAND_ORANGE


def sayit_mark(size: int = 64, color: str = BRAND_ORANGE) -> QPixmap:
    """Return the geometric SayIt SI monogram used across the app."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    c = QColor(color)
    s = float(size)
    stroke = max(2.0, s * 0.105)
    p.setPen(QPen(c, stroke, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)

    # Bold geometric S.
    path_s = QPainterPath()
    path_s.moveTo(s * 0.42, s * 0.27)
    path_s.cubicTo(s * 0.28, s * 0.20, s * 0.16, s * 0.28, s * 0.17, s * 0.39)
    path_s.cubicTo(s * 0.18, s * 0.50, s * 0.33, s * 0.49, s * 0.43, s * 0.54)
    path_s.cubicTo(s * 0.53, s * 0.59, s * 0.51, s * 0.75, s * 0.36, s * 0.77)
    path_s.cubicTo(s * 0.25, s * 0.79, s * 0.17, s * 0.73, s * 0.14, s * 0.68)
    p.drawPath(path_s)

    # Strong vertical I with compact angled accents.
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(c))
    i_x = s * 0.58
    i_y = s * 0.22
    i_w = s * 0.12
    i_h = s * 0.56
    p.drawRoundedRect(i_x, i_y, i_w, i_h, i_w / 2, i_w / 2)
    p.drawPolygon([
        QPointF(i_x + i_w * 0.05, i_y),
        QPointF(i_x + i_w * 0.95, i_y),
        QPointF(i_x + i_w * 1.38, i_y + s * 0.09),
        QPointF(i_x + i_w * 0.50, i_y + s * 0.09),
    ])
    p.drawPolygon([
        QPointF(i_x + i_w * 0.05, i_y + i_h),
        QPointF(i_x + i_w * 0.95, i_y + i_h),
        QPointF(i_x + i_w * 1.38, i_y + i_h - s * 0.09),
        QPointF(i_x + i_w * 0.50, i_y + i_h - s * 0.09),
    ])

    p.end()
    return pm


def sayit_icon(size: int = 64, color: str = BRAND_ORANGE) -> QIcon:
    return QIcon(sayit_mark(size, color))


# Calm, neutral stylesheet. Deliberately light-touch: it sets spacing,
# radii, and restrained borders/typography without hard-coding a full dark/light
# palette, so it coexists with the system theme and the overlay's own styling.
STYLESHEET = """
QWidget {
    font-size: 13px;
}
QDialog, QWidget#SayItMainWindow {
    /* leave background to the platform palette for light/dark friendliness */
}
QGroupBox {
    border: 1px solid rgba(128, 128, 128, 60);
    border-radius: 10px;
    margin-top: 14px;
    padding: 10px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}
QPushButton {
    border: 1px solid rgba(128, 128, 128, 70);
    border-radius: 8px;
    padding: 6px 14px;
}
QPushButton:hover {
    border-color: rgba(59, 156, 140, 160);
}
QPushButton:pressed {
    background: rgba(59, 156, 140, 30);
}
QPushButton:focus {
    border: 2px solid #3B9C8C;
    outline: none;
}
QPushButton:disabled {
    color: rgba(128, 128, 128, 160);
}
QComboBox, QLineEdit, QKeySequenceEdit {
    border: 1px solid rgba(128, 128, 128, 70);
    border-radius: 8px;
    padding: 5px 8px;
    min-height: 20px;
}
QComboBox:focus, QLineEdit:focus {
    border: 2px solid #3B9C8C;
}
QListWidget {
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 8px;
}
QListWidget::item:selected {
    background: rgba(59, 156, 140, 45);
    color: palette(text);
}
QProgressBar {
    border: 1px solid rgba(128, 128, 128, 70);
    border-radius: 6px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #3B9C8C;
    border-radius: 5px;
}
"""
