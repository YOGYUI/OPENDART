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
from businessReportModule import BusinessReportSubWindow
from ShareDisclosureModule import ShareDisclosureSubWindow
from setApiKeyModule import SetApiKeyDialog
from Util.functions import *
from uiCommon import makeQAction
# TODO: API Key Modify Module


class MainWindow(QMainWindow):
    _opendart: Union[OpenDart, None] = None

    _mdiArea: MyMDIArea
    _subwnd_list: List[QMdiSubWindow]

    _subwnd_company_info: CompanyInformationSubWindow
    _subwnd_daily_docs: DailyDocumentSubWindow
    _subwnd_search_doc: SearchDocumentSubWindow
    _subwnd_corp_list: CorporationListSubWindow
    _subwnd_business_report: BusinessReportSubWindow
    _subwnd_share_disclosure: ShareDisclosureSubWindow

    _menu_visible_subwnd_company_info: QAction
    _menu_visible_subwnd_daily_docs: QAction
    _menu_visible_subwnd_search_doc: QAction
    _menu_visible_subwnd_corp_list: QAction
    _menu_visible_business_report: QAction
    _menu_visible_share_disclosure: QAction

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)

        self._mdiArea = MyMDIArea(self)
        self._subwnd_list = list()
        self._subwnd_company_info = CompanyInformationSubWindow(dart_obj, self)
        self._subwnd_daily_docs = DailyDocumentSubWindow(dart_obj, self)
        self._subwnd_search_doc = SearchDocumentSubWindow(dart_obj, self)
        self._subwnd_corp_list = CorporationListSubWindow(dart_obj, self)
        self._subwnd_business_report = BusinessReportSubWindow(dart_obj, self)
        self._subwnd_share_disclosure = ShareDisclosureSubWindow(dart_obj, self)

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
        self._mdiArea.addSubWindow(self._subwnd_business_report)
        self._subwnd_list.append(self._subwnd_business_report)
        self._mdiArea.addSubWindow(self._subwnd_share_disclosure)
        self._subwnd_list.append(self._subwnd_share_disclosure)

        for wnd in self._subwnd_list:
            wnd.resize(600, 600)
        self._mdiArea.cascadeSubWindows()

    def initMenuBar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        menuFile = QMenu('&File', menubar)
        menubar.addAction(menuFile.menuAction())
        menu_close = makeQAction(parent=self, text="Close", triggered=self.close)
        menuFile.addAction(menu_close)

        menuView = QMenu('&View', menubar)
        menubar.addAction(menuView.menuAction())
        menuView.aboutToShow.connect(self.onMenuViewAboutToShow)
        self._menu_visible_subwnd_company_info = makeQAction(
            parent=self, text="Company Information", checkable=True,
            triggered=lambda: self.toggleSubWindowVisible(self._subwnd_company_info))
        self._menu_visible_subwnd_company_info.setIcon(self._subwnd_company_info.windowIcon())
        menuView.addAction(self._menu_visible_subwnd_company_info)
        self._menu_visible_subwnd_daily_docs = makeQAction(
            parent=self, text="Daily Document List", checkable=True,
            triggered=lambda: self.toggleSubWindowVisible(self._subwnd_daily_docs))
        self._menu_visible_subwnd_daily_docs.setIcon(self._subwnd_daily_docs.windowIcon())
        menuView.addAction(self._menu_visible_subwnd_daily_docs)
        self._menu_visible_subwnd_search_doc = makeQAction(
            parent=self, text="Search Document", checkable=True,
            triggered=lambda: self.toggleSubWindowVisible(self._subwnd_search_doc))
        self._menu_visible_subwnd_search_doc.setIcon(self._subwnd_search_doc.windowIcon())
        menuView.addAction(self._menu_visible_subwnd_search_doc)
        self._menu_visible_subwnd_corp_list = makeQAction(
            parent=self, text="Corporation List", checkable=True,
            triggered=lambda: self.toggleSubWindowVisible(self._subwnd_corp_list))
        self._menu_visible_subwnd_corp_list.setIcon(self._subwnd_corp_list.windowIcon())
        menuView.addAction(self._menu_visible_subwnd_corp_list)
        self._menu_visible_business_report = makeQAction(
            parent=self, text="Business Report Detail", checkable=True,
            triggered=lambda: self.toggleSubWindowVisible(self._subwnd_business_report))
        self._menu_visible_business_report.setIcon(self._subwnd_business_report.windowIcon())
        menuView.addAction(self._menu_visible_business_report)
        self._menu_visible_share_disclosure = makeQAction(
            parent=self, text="Share Disclosure Detail", checkable=True,
            triggered=lambda: self.toggleSubWindowVisible(self._subwnd_share_disclosure))
        self._menu_visible_share_disclosure.setIcon(self._subwnd_share_disclosure.windowIcon())
        menuView.addAction(self._menu_visible_share_disclosure)
        menuView.addSeparator()

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
        self._subwnd_business_report.setCorporationCode(corp_code)
        self._subwnd_share_disclosure.setCorporationCode(corp_code)

    def setSearchCorporationName(self, corp_name: str):
        self._subwnd_search_doc.setCorporationName(corp_name)

    def showEvent(self, a0: QShowEvent) -> None:
        self.setCenterWindow()

    def closeEvent(self, a0: QCloseEvent) -> None:
        self.release()

    @staticmethod
    def toggleSubWindowVisible(subwnd: QMdiSubWindow):
        if subwnd.isVisible():
            subwnd.hide()
        else:
            subwnd.showNormal()
            subwnd.show()

    def onMenuViewAboutToShow(self):
        self._menu_visible_subwnd_company_info.setChecked(self._subwnd_company_info.isVisible())
        self._menu_visible_subwnd_daily_docs.setChecked(self._subwnd_daily_docs.isVisible())
        self._menu_visible_subwnd_search_doc.setChecked(self._subwnd_search_doc.isVisible())
        self._menu_visible_subwnd_corp_list.setChecked(self._subwnd_corp_list.isVisible())
        self._menu_visible_business_report.setChecked(self._subwnd_business_report.isVisible())
        self._menu_visible_share_disclosure.setChecked(self._subwnd_share_disclosure.isVisible())

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
    wnd_.resize(800, 800)

    app.exec_()
