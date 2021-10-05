from PyQt5.QtWidgets import QMdiArea


class MyMDIArea(QMdiArea):
    def __init__(self, parent=None):
        super().__init__(parent)
