import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QCoreApplication


def onIconUrlChanged(url: QUrl):
    print(url)


def onIconChanged(icon: QIcon):
    pixmap = icon.pixmap(16, 16)
    pixmap.save('./dart.ico', 'ico')


app = QCoreApplication.instance()
if app is None:
    app = QApplication(sys.argv)

view = QWebEngineView()
view.iconUrlChanged.connect(onIconUrlChanged)
view.iconChanged.connect(onIconChanged)
view.setUrl(QUrl("https://dart.fss.or.kr/"))
view.show()
app.exec_()
