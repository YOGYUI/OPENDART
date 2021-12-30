from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPaintEvent, QPainter, QBrush, QColor, QFont
from PyQt5.QtWidgets import QMdiArea


class MyMDIArea(QMdiArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_text = ''

    def paintEvent(self, paintEvent: QPaintEvent) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(paintEvent.rect(), QBrush(Qt.white))
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont('Decorative', 12))
        painter.drawText(5, 5, self.width(), 350, Qt.AlignLeft, self._display_text)

    def setDisplayText(self, text: str):
        self._display_text = text
