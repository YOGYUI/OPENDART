# Author: Yogyui
from PyQt5.QtWidgets import QMainWindow
from opendart import OpenDart


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.initControl()
        self.initLayout()

    def release(self):
        pass

    def initLayout(self):
        pass

    def initControl(self):
        pass
