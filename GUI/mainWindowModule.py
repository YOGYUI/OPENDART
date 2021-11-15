import os
import sys
from typing import Union, List
from PyQt5.QtGui import QShowEvent, QCloseEvent
from PyQt5.QtWidgets import QMainWindow, QMdiSubWindow, QMessageBox, QMenu, QMenuBar, QDesktopWidget
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart
from mdiAreaModule import MyMDIArea
from companyInformationModule import CompanyInformationSubWindow
from dailyDocumentModule import DailyDocumentSubWindow
from searchDocumentModule import SearchDocumentSubWindow
from documentViewerModule import DocumentViewerSubWindow
from corporationListModule import CorporationListSubWindow
from setApiKeyModule import SetApiKeyDialog
from Util.functions import *


class MainWindow(QMainWindow):
    _opendart: Union[OpenDart, None] = None

    _mdiArea: MyMDIArea
    _subwnd_list: List[QMdiSubWindow]
    _subwnd_company_info: CompanyInformationSubWindow
    _subwnd_daily_docs: DailyDocumentSubWindow
    _subwnd_search_doc: SearchDocumentSubWindow
    _subwnd_corp_list: CorporationListSubWindow

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)

        self._mdiArea = MyMDIArea(self)
        self._subwnd_list = list()
        self._subwnd_company_info = CompanyInformationSubWindow(dart_obj, self)
        self._subwnd_daily_docs = DailyDocumentSubWindow(dart_obj, self)
        self._subwnd_search_doc = SearchDocumentSubWindow(dart_obj, self)
        self._subwnd_corp_list = CorporationListSubWindow(dart_obj, self)

        self.initControl()
        self.initLayout()
        self._menuBar = QMenuBar(self)
        self.initMenuBar()
        self.setOpenDartObject(dart_obj)
        self.setWindowTitle('DART Application')
        self.resize(800, 800)

    def release(self):
        if self._opendart is not None:
            self._opendart.release()

    def initLayout(self):
        self.setCentralWidget(self._mdiArea)

    def initControl(self):
        self._mdiArea.addSubWindow(self._subwnd_company_info)
        self._subwnd_list.append(self._subwnd_company_info)
        self._mdiArea.addSubWindow(self._subwnd_daily_docs)
        self._subwnd_daily_docs.sig_open_document.connect(self.openDocument)
        self._subwnd_daily_docs.sig_corporation_code.connect(self.loadCompanyInformation)
        self._subwnd_list.append(self._subwnd_daily_docs)
        self._mdiArea.addSubWindow(self._subwnd_search_doc)
        self._subwnd_search_doc.sig_open_document.connect(self.openDocument)
        self._subwnd_search_doc.sig_corporation_code.connect(self.loadCompanyInformation)
        self._subwnd_list.append(self._subwnd_search_doc)
        self._mdiArea.addSubWindow(self._subwnd_corp_list)
        self._subwnd_corp_list.sig_corporation_code.connect(self.loadCompanyInformation)
        self._subwnd_corp_list.sig_corporation_name.connect(self.setSearchCorporationName)
        self._subwnd_list.append(self._subwnd_corp_list)
        self._mdiArea.cascadeSubWindows()

    def initMenuBar(self):
        self.setMenuBar(self._menuBar)

        menuFile = QMenu('File', self._menuBar)
        self._menuBar.addAction(menuFile.menuAction())
        menu_set_apikey = makeQAction(parent=self, text='Set API Key', triggered=self.openSetApiKeyDialog)
        menuFile.addAction(menu_set_apikey)
        menuFile.addSeparator()
        menu_close = makeQAction(parent=self, text='Close', triggered=self.close)
        menuFile.addAction(menu_close)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj
        self._opendart.registerCallbackApiResponseException(self.onOpenDartApiResponseException)
        for swnd in self._subwnd_list:
            if callable(getattr(swnd, 'setOpenDartObject', None)):
                swnd.setOpenDartObject(obj)

    def onOpenDartApiResponseException(self, status_code: int, message: str):
        QMessageBox.warning(self, 'API Response Exception', f'{status_code}: {message}')

    def openDocument(self, document_no: str):
        find = list(filter(lambda x: x.windowTitle() == document_no, self._subwnd_list))
        if len(find) > 0:
            subwnd = find[0]
        else:
            subwnd = DocumentViewerSubWindow(self._opendart, self)
            subwnd.sig_close.connect(self.onDocumentViewerSubWindowClosed)
            subwnd.setDocumentNumber(document_no)
            self._mdiArea.addSubWindow(subwnd)
            self._subwnd_list.append(subwnd)
        subwnd.showNormal()
        subwnd.show()
        subwnd.setFocus()

    def onDocumentViewerSubWindowClosed(self, subwnd: QMdiSubWindow):
        self._mdiArea.removeSubWindow(subwnd)
        self._subwnd_list.remove(subwnd)

    def loadCompanyInformation(self, corp_code: str):
        self._subwnd_company_info.setCorporationCodeAndRefresh(corp_code)

    def setSearchCorporationName(self, corp_name: str):
        self._subwnd_search_doc.setCorporationName(corp_name)

    def showEvent(self, a0: QShowEvent) -> None:
        self.setCenterWindow()

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.release()

    def setCenterWindow(self):
        qtRect = self.frameGeometry()
        centerPt = QDesktopWidget().availableGeometry().center()
        qtRect.moveCenter(centerPt)
        self.move(qtRect.topLeft())

    def openSetApiKeyDialog(self):
        dlg = SetApiKeyDialog(self)
        dlg.sig_set_key.connect(self.onApiKeyDialogSet)
        dlg.exec_()

    def onApiKeyDialogSet(self, key: str):
        try:
            self._opendart.setApiKey(key)
        except Exception as e:
            QMessageBox.warning(self, 'Exception', str(e))


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wnd_ = MainWindow(dart)
    wnd_.show()

    app.exec_()
