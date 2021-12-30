from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QDialog, QWidget, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout


class SetApiKeyDialog(QDialog):
    sig_set_key = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._editApiKey = QLineEdit()
        self._btnApply = QPushButton('Apply')
        self._btnCancel = QPushButton('Cancel')
        self.initControl()
        self.initLayout()
        self.setWindowTitle('Set API Key')
        self.setMinimumWidth(400)

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.setSpacing(4)
        vbox.addWidget(self._editApiKey)

        subwgt = QWidget()
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setAlignment(Qt.AlignRight)
        hbox.addWidget(self._btnApply)
        hbox.addWidget(self._btnCancel)
        vbox.addWidget(subwgt)

    def initControl(self):
        self._editApiKey.setPlaceholderText('Type API Key')
        self._btnApply.clicked.connect(self.onClickBtnApply)
        self._btnCancel.clicked.connect(self.close)

    def onClickBtnApply(self):
        key_string = self._editApiKey.text()
        self.sig_set_key.emit(key_string)
        self.close()

    def setCurrentKey(self, key: str):
        self._editApiKey.setText(key)


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    dlg_ = SetApiKeyDialog()
    dlg_.exec_()
