from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPaintEvent, QPixmap, QPainter, QBrush, QColor, QFont
from PyQt5.QtWidgets import QMdiArea


class MyMDIArea(QMdiArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._display_text = ''
        self._pixmap1 = QPixmap('./Resource/opendart_logo.png')
        self._pixmap2 = QPixmap('./Resource/fss_logo.jpg')
        self._pixmap2 = self._pixmap2.scaledToWidth(100)
        self.setDisplayText('[DART Application]')
        self.setDisplayText('금융감독원 OpenAPI 공시정보 활용 어플리케이션\n')
        self.setDisplayText('개발자: YOGYUI')

    def paintEvent(self, paintEvent: QPaintEvent) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(paintEvent.rect(), QBrush(Qt.white))
        painter.setPen(QColor(0, 0, 0))
        painter.setFont(QFont('Decorative', 12))
        painter.drawText(5, 5, self.width(), 350, Qt.AlignLeft, self._display_text)

        px1w, px1h = self._pixmap1.width(), self._pixmap1.height()
        x, y = 0, self.height() - px1h
        painter.drawPixmap(x, y, px1w, px1h, self._pixmap1)

        px2w, px2h = self._pixmap2.width(), self._pixmap2.height()
        x, y = self.width() - px2w, self.height() - px2h
        painter.drawPixmap(x, y, px2w, px2h, self._pixmap2)

    def setDisplayText(self, text: str):
        self._display_text += text + '\n'
