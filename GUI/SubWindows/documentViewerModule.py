import os
import re
import sys
import time
from functools import partial
from typing import Union, List
from PyQt5.QtCore import QUrl, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QLabel, QRadioButton, QButtonGroup, QMessageBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy, QTabWidget, QTabBar
from PyQt5.QtWidgets import QMdiSubWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart


class ThreadDownloadDocument(QThread):
    sig_doc_html_path = pyqtSignal(str)
    sig_terminated = pyqtSignal()

    def __init__(self, opendart: OpenDart, document_no: str):
        super().__init__()
        self._opendart = opendart
        self._document_no = document_no
        self.setObjectName(f'Download Document({document_no})')

    def run(self):
        doc_html_path = self._opendart.downloadDocumentAsHtmlFile(self._document_no)
        self.sig_doc_html_path.emit(doc_html_path)
        self.sig_terminated.emit()


class DocumentViewerWidget(QWidget):
    _opendart: Union[OpenDart, None] = None
    _threadDownload: Union[ThreadDownloadDocument, None] = None

    sig_title = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widgetDocumentNumber = QWidget()
        self._editDocumentNumber = QLineEdit()
        self._btnLoadDocument = QPushButton()
        self._radioLoadDartPage = QRadioButton('DART Web Page')
        self._radioLoadHtmlFile = QRadioButton('HTML File')
        self._webview = QWebEngineView()
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)

    def release(self):
        self._webview.close()

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def setDocumentNumber(self, no: str, load: bool = True):
        self._editDocumentNumber.setText(no)
        if load:
            self.loadDocument()

    def getDocumentNumber(self) -> str:
        return self._editDocumentNumber.text()

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(6)

        self._widgetDocumentNumber = QWidget()
        self._widgetDocumentNumber.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(self._widgetDocumentNumber)
        hbox.setContentsMargins(4, 0, 0, 0)
        hbox.setSpacing(8)
        lbl = QLabel('Document #')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editDocumentNumber)
        hbox.addWidget(self._btnLoadDocument)
        vbox.addWidget(self._widgetDocumentNumber)
        self._widgetDocumentNumber.hide()

        vbox.addWidget(self._webview)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        hbox.addWidget(QWidget())
        self._radioLoadDartPage.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioLoadDartPage)
        self._radioLoadHtmlFile.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioLoadHtmlFile)
        vbox.addWidget(subwgt)

    def initControl(self):
        self._btnLoadDocument.clicked.connect(self.loadDocument)
        self._editDocumentNumber.returnPressed.connect(self.loadDocument)
        btngrp = QButtonGroup()
        btngrp.addButton(self._radioLoadDartPage)
        self._radioLoadDartPage.clicked.connect(self.loadDocument)
        btngrp.addButton(self._radioLoadHtmlFile)
        self._radioLoadHtmlFile.clicked.connect(self.loadDocument)
        self._radioLoadHtmlFile.setChecked(True)

    def loadDocument(self):
        document_no = self._editDocumentNumber.text().strip()
        regex = re.compile(r"^[0-9]{14}$")

        url = QUrl('about:blank')
        tm_start = time.perf_counter()
        if regex.search(document_no) is not None:
            if self._radioLoadHtmlFile.isChecked():
                if self._opendart is None:
                    QMessageBox.warning(self, "Warning", "Open DART object is None!")
                else:
                    doc_html_path = self._opendart.downloadDocumentAsHtmlFile(document_no)
                    if os.path.isfile(doc_html_path):
                        url = QUrl.fromLocalFile(doc_html_path)
                    # self.startThreadDownload(document_no)
            else:
                url = QUrl(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={document_no}")
            self.sig_title.emit(document_no)
        else:
            QMessageBox.warning(self, 'Warning', 'Document Number String Format Error!')
            self.sig_title.emit('Null')
        elapsed = time.perf_counter() - tm_start
        self._opendart.log(f'complete webview loading (elapsed: {elapsed} sec)')
        self._webview.load(url)

    def startThreadDownload(self, document_no: str):
        if self._threadDownload is None:
            self._threadDownload = ThreadDownloadDocument(self._opendart, document_no)
            self._threadDownload.sig_doc_html_path.connect(self.onThreadDownloadDone)
            self._threadDownload.sig_terminated.connect(self.onThreadDownloadTerminated)
            self._threadDownload.start()

    def onThreadDownloadDone(self, html_path: str):
        if os.path.isfile(html_path):
            url = QUrl.fromLocalFile(html_path)
            self._webview.load(url)

    def onThreadDownloadTerminated(self):
        del self._threadDownload
        self._threadDownload = None

    def setDocumentNumberEditVisible(self, visible: bool):
        self._widgetDocumentNumber.setVisible(visible)

    def isDocumentNumberEditVisible(self) -> bool:
        return self._widgetDocumentNumber.isVisible()


class DocumentViewerSubWindow(QMdiSubWindow):
    _dart_obj: Union[OpenDart, None] = None
    _doc_widget_list: List[DocumentViewerWidget]

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._dart_obj = dart_obj
        self._btnSave = QPushButton('SAVE')
        self._tabWidget = QTabWidget()
        self._doc_widget_list = list()
        self.setWindowTitle('공시 문서 뷰어')
        self.initControl()
        self.initLayout()
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)

    def release(self):
        self.closeAllTab()

    def initLayout(self):
        widget = QWidget()
        vbox = QVBoxLayout(widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        """
        subwgt = QWidget()
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(4, 4, 4, 0)
        hbox.setSpacing(4)
        hbox.addWidget(self._btnSave)
        hbox.addWidget(QWidget())
        vbox.addWidget(subwgt)
        """
        vbox.addWidget(self._tabWidget)
        self.setWidget(widget)

    def initControl(self):
        self._tabWidget.setTabPosition(QTabWidget.North)
        self._tabWidget.setMovable(True)
        self._btnSave.clicked.connect(self.onClickBtnSave)

    def setOpenDartObject(self, obj: OpenDart):
        for widget in self._doc_widget_list:
            widget.setOpenDartObject(obj)

    def setDocumentNumber(self, document_no: str, load: bool = True):
        doc_no_list = [x.getDocumentNumber() for x in self._doc_widget_list]
        if document_no in doc_no_list:
            index = doc_no_list.index(document_no)
            self._tabWidget.setCurrentIndex(index)
        else:
            widget = DocumentViewerWidget(self._dart_obj, self)
            self._doc_widget_list.append(widget)
            self._tabWidget.addTab(widget, document_no)
            index = self._tabWidget.indexOf(widget)
            btn = QPushButton()
            btn.setIcon(QIcon('./Resource/close.png'))
            btn.setFlat(True)
            btn.setFixedSize(16, 16)
            btn.setIconSize(QSize(14, 14))
            btn.clicked.connect(partial(self.closeTab, widget))
            self._tabWidget.tabBar().setTabButton(index, QTabBar.RightSide, btn)
            self._tabWidget.setCurrentIndex(index)
            widget.setDocumentNumber(document_no, load)

    def closeTab(self, viewer: DocumentViewerWidget):
        index = self._tabWidget.indexOf(viewer)
        self._tabWidget.removeTab(index)
        self._doc_widget_list.remove(viewer)
        viewer.release()

    def closeAllTab(self):
        for widget in self._doc_widget_list:
            index = self._tabWidget.indexOf(widget)
            self._tabWidget.removeTab(index)
            widget.release()

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def onClickBtnSave(self):
        try:
            wgt = self._tabWidget.currentWidget()
            if isinstance(wgt, DocumentViewerWidget):
                doc_no = wgt.getDocumentNumber()
                self._dart_obj.downloadDocumentRawFile(doc_no)
        except Exception:
            pass


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    subwnd_ = DocumentViewerSubWindow(dart)
    subwnd_.show()
    subwnd_.resize(600, 600)

    app.exec_()
