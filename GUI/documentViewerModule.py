import os
import re
import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QLabel, QRadioButton, QButtonGroup, QMessageBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt5.QtWebEngineWidgets import QWebEngineView
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart


class DocumentViewerWidget(QWidget):
    _opendart: OpenDart

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._editDocumentNumber = QLineEdit()
        self._btnLoadDocument = QPushButton()
        self._radioLoadDartPage = QRadioButton('DART Page')
        self._radioLoadHtmlFile = QRadioButton('HTML File')
        self._webview = QWebEngineView()
        self.initControl()
        self.initLayout()

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def setDocumentNumber(self, no: str, load: bool = True):
        self._editDocumentNumber.setText(no)
        if load:
            self.loadDocument()

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 6, 4, 4)
        vbox.setSpacing(6)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(4, 0, 0, 0)
        hbox.setSpacing(8)
        lbl = QLabel('Document #')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editDocumentNumber)
        hbox.addWidget(self._btnLoadDocument)
        vbox.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        self._radioLoadDartPage.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioLoadDartPage)
        self._radioLoadHtmlFile.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioLoadHtmlFile)
        hbox.addWidget(QWidget())
        vbox.addWidget(subwgt)

        vbox.addWidget(self._webview)

    def initControl(self):
        self._btnLoadDocument.clicked.connect(self.loadDocument)
        self._editDocumentNumber.returnPressed.connect(self.loadDocument)
        btngrp = QButtonGroup()
        btngrp.addButton(self._radioLoadDartPage)
        btngrp.addButton(self._radioLoadHtmlFile)
        self._radioLoadHtmlFile.setChecked(True)

    def loadDocument(self):
        document_no = self._editDocumentNumber.text().strip()
        regex = re.compile(r"^[0-9]{14}$")

        url = QUrl('about:blank')
        if regex.search(document_no) is not None:
            if self._radioLoadHtmlFile.isChecked():
                doc_html_path = self._opendart.downloadDocumentAsHtmlFile(document_no)
                if os.path.isfile(doc_html_path):
                    url = QUrl.fromLocalFile(doc_html_path)
            else:
                url = QUrl(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={document_no}")
        else:
            QMessageBox.warning(self, 'Warning', 'Document Number String Format Error!')
        self._webview.load(url)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = DocumentViewerWidget()
    wgt_.setOpenDartObject(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
