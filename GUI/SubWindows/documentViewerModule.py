import os
import re
import sys
import time
from functools import partial
from typing import Union, List
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QSize, QPoint
from PyQt5.QtGui import QCloseEvent, QIcon
from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QLabel, QRadioButton, QButtonGroup, QMessageBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy, QTabWidget, QTabBar, QFileDialog
from PyQt5.QtWidgets import QMdiSubWindow, QMenu
from PyQt5.QtWebEngineWidgets import QWebEngineView
CURPATH = os.path.dirname(os.path.abspath(__file__))
GUIPATH = os.path.dirname(CURPATH)
PROJPATH = os.path.dirname(GUIPATH)
sys.path.extend([CURPATH, GUIPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, GUIPATH, PROJPATH
from opendart import OpenDart
from uiCommon import makeQAction


class DocumentViewerWidget(QWidget):
    _opendart: Union[OpenDart, None] = None

    sig_doc_number = pyqtSignal(QWidget, str)
    sig_doc_title = pyqtSignal(QWidget, str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widgetDocumentNumber = QWidget()
        self._editDocumentNumber = QLineEdit()
        self._widgetDocumentTitle = QWidget()
        self._editDocumentTitle = QLineEdit()
        self._editCorpCode = QLineEdit()
        self._editCorpName = QLineEdit()
        self._btnSaveToHtml = QPushButton()
        self._btnPrintToPdf = QPushButton()
        self._editUrl = QLineEdit()
        self._radioLoadDartPage = QRadioButton('DART 웹페이지')
        self._radioLoadHtmlFile = QRadioButton('HTML 파일')
        self._webviewDart = QWebEngineView()
        self._webviewHtml = QWebEngineView()
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)

    def release(self):
        self._webviewDart.close()
        self._webviewHtml.close()

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
        vbox.setContentsMargins(0, 4, 0, 2)
        vbox.setSpacing(6)

        self._widgetDocumentNumber.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(self._widgetDocumentNumber)
        hbox.setContentsMargins(4, 0, 4, 0)
        hbox.setSpacing(8)
        lbl = QLabel('문서번호')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editDocumentNumber)
        lbl = QLabel('회사명')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editCorpName)
        lbl = QLabel('회사고유번호')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editCorpCode)
        hbox.addWidget(self._btnSaveToHtml)
        hbox.addWidget(self._btnPrintToPdf)
        vbox.addWidget(self._widgetDocumentNumber)

        self._widgetDocumentTitle.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(self._widgetDocumentTitle)
        hbox.setContentsMargins(4, 0, 4, 0)
        hbox.setSpacing(8)
        lbl = QLabel('문서제목')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editDocumentTitle)
        vbox.addWidget(self._widgetDocumentTitle)

        vbox.addWidget(self._webviewDart)
        vbox.addWidget(self._webviewHtml)
        self._webviewDart.setVisible(False)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(4, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('URL')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editUrl)
        self._radioLoadDartPage.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioLoadDartPage)
        self._radioLoadHtmlFile.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioLoadHtmlFile)
        vbox.addWidget(subwgt)

    def initControl(self):
        self._editDocumentNumber.setReadOnly(False)
        self._editDocumentNumber.returnPressed.connect(self.loadDocument)
        self._editDocumentTitle.setReadOnly(True)
        self._editCorpName.setReadOnly(True)
        self._editCorpCode.setReadOnly(True)
        self._editUrl.setReadOnly(True)
        self._btnSaveToHtml.setIcon(QIcon('./Resource/file_html.png'))
        self._btnSaveToHtml.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._btnSaveToHtml.setToolTip('HTML로 저장')
        self._btnSaveToHtml.clicked.connect(self.onClickBtnSaveToHtml)
        self._btnPrintToPdf.setIcon(QIcon('./Resource/file_pdf.png'))
        self._btnPrintToPdf.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._btnPrintToPdf.setToolTip('PDF로 저장')
        self._btnPrintToPdf.clicked.connect(self.onClickBtnPrintToPdf)
        btngrp = QButtonGroup()
        btngrp.addButton(self._radioLoadDartPage)
        self._radioLoadDartPage.clicked.connect(self.onClickRadioViewer)
        btngrp.addButton(self._radioLoadHtmlFile)
        self._radioLoadHtmlFile.clicked.connect(self.onClickRadioViewer)
        self._radioLoadHtmlFile.setChecked(True)
        self._webviewDart.titleChanged.connect(self.onWebViewTitleChanged)
        self._webviewDart.loadFinished.connect(self.onWebViewLoadFinished)
        self._webviewDart.page().pdfPrintingFinished.connect(self.onWebViewPdfPrintingFinished)
        self._webviewHtml.page().pdfPrintingFinished.connect(self.onWebViewPdfPrintingFinished)

    def loadDocument(self):
        document_no = self._editDocumentNumber.text().strip()
        regex = re.compile(r"^[0-9]{14}$")

        url = QUrl('about:blank')
        self._webviewHtml.load(url)
        self._webviewDart.load(url)
        self._editCorpCode.clear()
        self._editCorpName.clear()
        self._editDocumentTitle.clear()
        self._editUrl.clear()
        tm_start = time.perf_counter()
        if regex.search(document_no) is not None:
            if self._opendart is None:
                QMessageBox.warning(self, "Warning", "Open DART object is None!")
            else:
                doc_html_path = self._opendart.downloadDocumentAsHtmlFile(document_no)
                if os.path.isfile(doc_html_path):
                    url = QUrl.fromLocalFile(doc_html_path)
                    self._webviewHtml.load(url)
                url = QUrl(f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={document_no}")
                self._webviewDart.load(url)
                self.sig_doc_number.emit(self, document_no)
                elapsed = time.perf_counter() - tm_start
                self._opendart.log(f'complete webview loading (elapsed: {elapsed} sec)')
        else:
            QMessageBox.warning(self, 'Warning', 'Document Number String Format Error!')

    def onWebViewTitleChanged(self, title: str):
        self._editDocumentTitle.setText(title)
        self.sig_doc_title.emit(self, title)

    def onWebViewLoadFinished(self, result: bool):
        self._editUrl.setText(self._webviewDart.url().url())
        if result:
            def callback_func(obj):
                try:
                    if isinstance(obj, dict):
                        innerText = obj.get('innerText')
                        if innerText is not None and isinstance(innerText, str):
                            self._editCorpName.setText(innerText)
                        onclick = obj.get('onclick')
                        if onclick is not None and isinstance(onclick, str):
                            if 'openCorpInfoNew' in onclick:
                                idx = onclick.find('(')
                                splt = onclick[idx + 1:].split(',')[0]
                                splt = splt.replace("'", "")
                                self._editCorpCode.setText(splt)
                except Exception as e:
                    print(e)

            script = """
                temp = null;
                nameWrapDiv = document.getElementsByClassName('nameWrap')[0];
                if (nameWrapDiv != null) {
                    span = nameWrapDiv.getElementsByTagName('span')[1];
                    if (span != null) {
                        temp = {'onclick': span.getAttribute('onclick'), 'innerText': span.innerText}
                    }
                }
                temp;
            """
            self._webviewDart.page().runJavaScript(script, callback_func)

    def onClickRadioViewer(self):
        if self._radioLoadHtmlFile.isChecked():
            self._webviewDart.setVisible(False)
            self._webviewHtml.setVisible(True)
        else:
            self._webviewDart.setVisible(True)
            self._webviewHtml.setVisible(False)

    def onClickBtnSaveToHtml(self):
        options = QFileDialog.Options()
        path, _ = QFileDialog.getSaveFileName(self, 'Select File', self._editDocumentNumber.text(),
                                              'HTML File (*.html)', options=options)
        if path:
            if self._webviewDart.isVisible():
                page = self._webviewDart.page()
            else:
                page = self._webviewHtml.page()

            def callback(html: str):
                with open(path, 'w') as fp:
                    fp.write(html)
                    QMessageBox.information(self, 'Information', 'HTML 파일 저장 완료')

            page.toHtml(callback)

    def onClickBtnPrintToPdf(self):
        options = QFileDialog.Options()
        path, _ = QFileDialog.getSaveFileName(self, 'Select File', self._editDocumentNumber.text(),
                                              'PDF File (*.pdf)', options=options)
        if path:
            if self._webviewDart.isVisible():
                page = self._webviewDart.page()
            else:
                page = self._webviewHtml.page()
            page.printToPdf(path)

    def onWebViewPdfPrintingFinished(self, filepath: str, result: bool):
        if result:
            QMessageBox.information(self, 'Information', f'PDF 파일 저장 완료\n{filepath}')
        else:
            QMessageBox.warning(self, 'Warning', 'PDF 파일 변환 실패')


class EmptyWidget(QWidget):
    sig_doc_number = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._editDocumentNumber = QLineEdit()
        self.initControl()
        self.initLayout()

    def release(self):
        pass

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 2)
        vbox.setSpacing(6)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(4, 0, 4, 0)
        hbox.setSpacing(8)
        lbl = QLabel('문서번호')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editDocumentNumber)
        vbox.addWidget(subwgt)
        vbox.addWidget(QWidget())

    def initControl(self):
        self._editDocumentNumber.setReadOnly(False)
        self._editDocumentNumber.returnPressed.connect(self.loadDocument)

    def setOpenDartObject(self, *args):
        pass

    def loadDocument(self):
        document_no = self._editDocumentNumber.text().strip()
        regex = re.compile(r"^[0-9]{14}$")
        if regex.search(document_no) is not None:
            self.sig_doc_number.emit(document_no)
        else:
            QMessageBox.warning(self, 'Warning', 'Document Number String Format Error!')

    @staticmethod
    def getDocumentNumber():
        return 'empty'


class DocumentViewerSubWindow(QMdiSubWindow):
    _dart_obj: Union[OpenDart, None] = None
    _doc_widget_list: List[Union[DocumentViewerWidget, EmptyWidget]]

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._dart_obj = dart_obj
        self._tabWidget = QTabWidget()
        self._doc_widget_list = list()
        self.setWindowTitle('공시 문서 뷰어')
        self.initControl()
        self.initLayout()
        self.setMinimumWidth(400)
        self.setMinimumHeight(400)

    def release(self):
        self.closeAllTab(False)

    def initLayout(self):
        widget = QWidget()
        vbox = QVBoxLayout(widget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)
        vbox.addWidget(self._tabWidget)
        self.setWidget(widget)

    def initControl(self):
        self._tabWidget.setTabPosition(QTabWidget.North)
        self._tabWidget.setMovable(True)
        self._tabWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tabWidget.customContextMenuRequested.connect(self.onTabWidgetContextMenuRequested)
        self.checkTabCount()

    def setOpenDartObject(self, obj: OpenDart):
        for widget in self._doc_widget_list:
            widget.setOpenDartObject(obj)

    def checkTabCount(self):
        if self._tabWidget.count() == 0:
            widget = EmptyWidget(self)
            widget.sig_doc_number.connect(self.setDocumentNumber)
            self._doc_widget_list.append(widget)
            self._tabWidget.addTab(widget, 'Empty')
        else:
            widget_list = list(filter(lambda x: isinstance(x, EmptyWidget), self._doc_widget_list))
            if len(widget_list) == 1:
                widget = widget_list[0]
                index = self._tabWidget.indexOf(widget)
                self._tabWidget.removeTab(index)
                self._doc_widget_list.remove(widget)

    def setDocumentNumber(self, document_no: str, load: bool = True):
        doc_no_list = [x.getDocumentNumber() for x in self._doc_widget_list]
        if document_no in doc_no_list:
            index = doc_no_list.index(document_no)
            self._tabWidget.setCurrentIndex(index)
        else:
            widget = DocumentViewerWidget(self._dart_obj, self)
            widget.sig_doc_number.connect(self.onDocumentViewerWidgetNumberChanged)
            widget.sig_doc_title.connect(self.onDocumentViewerWidgetTitleChanged)
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
        self.checkTabCount()

    def closeTab(self, viewer: Union[DocumentViewerWidget, EmptyWidget]):
        index = self._tabWidget.indexOf(viewer)
        self._tabWidget.removeTab(index)
        self._doc_widget_list.remove(viewer)
        viewer.release()
        self.checkTabCount()

    def closeAllTab(self, checkTab: bool = True):
        for widget in self._doc_widget_list:
            index = self._tabWidget.indexOf(widget)
            self._tabWidget.removeTab(index)
            self._doc_widget_list.remove(widget)
            widget.release()
        if checkTab:
            self.checkTabCount()

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

    def onDocumentViewerWidgetNumberChanged(self, viewer: Union[DocumentViewerWidget], doc_no: str):
        index = self._tabWidget.indexOf(viewer)
        self._tabWidget.tabBar().setTabText(index, doc_no)

    def onDocumentViewerWidgetTitleChanged(self, viewer: Union[DocumentViewerWidget], title: str):
        index = self._tabWidget.indexOf(viewer)
        self._tabWidget.tabBar().setTabToolTip(index, title)

    def onTabWidgetContextMenuRequested(self, point: QPoint):
        if point.isNull():
            return
        index = self._tabWidget.tabBar().tabAt(point)
        widget = self._tabWidget.widget(index)
        menu = QMenu(self)
        menuCloseTab = makeQAction(parent=self, text='탭 닫기', triggered=lambda: self.closeTab(widget))
        menu.addAction(menuCloseTab)
        menuCloseOthers = makeQAction(parent=self, text='모든 탭 닫기', triggered=lambda: self.closeAllTab())
        menu.addAction(menuCloseOthers)
        menu.exec(self._tabWidget.tabBar().mapToGlobal(point))


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
