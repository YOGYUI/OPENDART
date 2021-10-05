import os
import sys
import pandas as pd
from typing import Union
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QMdiSubWindow
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart


class CorporationListWidget(QWidget):
    _opendart: Union[OpenDart, None] = None

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(8)

    def initControl(self):
        pass

    def refresh(self):
        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return


class CorporationListSubWindow(QMdiSubWindow):
    _widget: CorporationListWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widget = CorporationListWidget(dart_obj, self)
        self.setWidget(self._widget)
        self.setWindowTitle('Corporation List')

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._widget.setOpenDartObject(obj)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wnd_ = CorporationListSubWindow(dart)
    wnd_.show()
    wnd_.resize(600, 600)

    app.exec_()
