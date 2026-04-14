from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def _make_preview_icon() -> QIcon:
    pm = QPixmap(18, 18)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(QColor("#47627f"))
    pen.setWidth(2)
    p.setPen(pen)
    p.drawEllipse(3, 3, 8, 8)
    p.drawLine(10, 10, 15, 15)
    p.end()
    return QIcon(pm)


def _make_app_icon() -> QIcon:
    """Create a simple built-in icon so we don't depend on external .ico files."""
    try:
        pm = QPixmap(32, 32)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor("#1b5e20")))
        p.setBrush(QBrush(QColor("#2e7d32")))
        p.drawRoundedRect(1, 1, 30, 30, 6, 6)
        p.setPen(QPen(QColor("white")))
        f = QFont()
        f.setBold(True)
        f.setPointSize(16)
        p.setFont(f)
        p.drawText(pm.rect(), Qt.AlignCenter, "V")
        p.end()
        return QIcon(pm)
    except Exception:
        return QIcon()


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        track_color = QColor("#4f93e6") if self._checked else QColor("#d8e1eb")
        border_color = QColor("#3e7fcd") if self._checked else QColor("#a8b8cb")
        p.setPen(QPen(border_color, 1))
        p.setBrush(track_color)
        p.drawRoundedRect(rect, 12, 12)

        knob_d = 18
        knob_y = (self.height() - knob_d) // 2
        knob_x = self.width() - knob_d - 3 if self._checked else 3
        p.setPen(QPen(QColor("#cfd9e4"), 1))
        p.setBrush(QColor("white"))
        p.drawEllipse(knob_x, knob_y, knob_d, knob_d)
        p.end()

