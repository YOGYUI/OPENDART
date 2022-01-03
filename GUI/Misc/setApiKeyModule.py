from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QWidget, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout


class SetApiKeyDialog(QDialog):
    sig_set_key = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._editApiKey = QLineEdit()
        self._btnApply = QPushButton('적용')
        self._btnCancel = QPushButton('취소')
        self.initControl()
        self.initLayout()
        self.setWindowTitle('OpenDART API Key 설정')
        self.setWindowIcon(QIcon('./Resource/key.png'))
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
        self._editApiKey.setPlaceholderText('OEPNDART API Key를 입력하세요')
        self._btnApply.clicked.connect(self.onClickBtnApply)
        self._btnApply.setIcon(QIcon('./Resource/check.png'))
        self._btnCancel.clicked.connect(self.onClickBtnCancel)
        self._btnCancel.setIcon(QIcon('./Resource/cancel.png'))

    def onClickBtnApply(self):
        key_string = self._editApiKey.text()
        self.sig_set_key.emit(key_string)
        self.close()

    def onClickBtnCancel(self):
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
