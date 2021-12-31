import os
import sys
from functools import partial
from typing import Union, List, Tuple
from PyQt5.QtGui import QShowEvent, QCloseEvent
from PyQt5.QtWidgets import QMainWindow, QMdiSubWindow, QMessageBox, QMenu, QMenuBar, QDesktopWidget
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart
from SubWindows import CompanyInformationSubWindow
from SubWindows import DailyDocumentSubWindow
from SubWindows import SearchDocumentSubWindow
from SubWindows import DocumentViewerSubWindow
from SubWindows import CorporationListSubWindow
from SubWindows import BusinessReportSubWindow
from SubWindows import ShareDisclosureSubWindow
from SubWindows import RegistrationStatementSubWindow
from SubWindows import MajorReportSubWindow
from SubWindows import FinanceInformationSubWindow
from Misc import SetApiKeyDialog
from Misc import MyMDIArea
from Util.functions import *
from uiCommon import makeQAction


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
    _subwnd_registration_statement: RegistrationStatementSubWindow
    _subwnd_major_report: MajorReportSubWindow
    _subwnd_financial_info: FinanceInformationSubWindow
    _subwnd_document_viewer: DocumentViewerSubWindow

    _menu_visible_subwnd_list: List[Tuple[QAction, QMdiSubWindow]]
    """
    _menu_visible_subwnd_company_info: QAction
    _menu_visible_subwnd_daily_docs: QAction
    _menu_visible_subwnd_search_doc: QAction
    _menu_visible_subwnd_corp_list: QAction
    _menu_visible_subwnd_business_report: QAction
    _menu_visible_subwnd_share_disclosure: QAction
    _menu_visible_subwnd_registration_statement: QAction
    _menu_visible_subwnd_major_report: QAction
    _menu_visible_subwnd_financial_info: QAction
    _menu_visible_subwnd_document_viewer: QAction
    """

    def __init__(self, dart_obj: OpenDart = None, parent=None, init_width: int = 800, init_height: int = 800):
        super().__init__(parent=parent)

        self._mdiArea = MyMDIArea(self)
        self._subwnd_list = list()
        self._subwnd_company_info = CompanyInformationSubWindow(dart_obj, self)
        self._subwnd_daily_docs = DailyDocumentSubWindow(dart_obj, self)
        self._subwnd_search_doc = SearchDocumentSubWindow(dart_obj, self)
        self._subwnd_corp_list = CorporationListSubWindow(dart_obj, self)
        self._subwnd_business_report = BusinessReportSubWindow(dart_obj, self)
        self._subwnd_share_disclosure = ShareDisclosureSubWindow(dart_obj, self)
        self._subwnd_registration_statement = RegistrationStatementSubWindow(dart_obj, self)
        self._subwnd_major_report = MajorReportSubWindow(dart_obj, self)
        self._subwnd_financial_info = FinanceInformationSubWindow(dart_obj, self)
        self._subwnd_document_viewer = DocumentViewerSubWindow(dart_obj, self)
        self._menu_visible_subwnd_list = list()

        self.initControl()
        self.initLayout()
        self.initMenuBar()
        self.setOpenDartObject(dart_obj)
        self.setWindowTitle('DART')
        self.setWindowIcon(QIcon('./Resource/dart.ico'))
        self.resize(init_width, init_height)

    def release(self):
        if self._opendart is not None:
            self._opendart.release()
        for subwnd in self._subwnd_list:
            if callable(getattr(subwnd, 'release', None)):
                subwnd.release()

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
        self._subwnd_business_report.sig_open_document.connect(self.openDocument)
        self._subwnd_list.append(self._subwnd_business_report)

        self._mdiArea.addSubWindow(self._subwnd_share_disclosure)
        self._subwnd_share_disclosure.sig_open_document.connect(self.openDocument)
        self._subwnd_list.append(self._subwnd_share_disclosure)

        self._mdiArea.addSubWindow(self._subwnd_registration_statement)
        self._subwnd_registration_statement.sig_open_document.connect(self.openDocument)
        self._subwnd_list.append(self._subwnd_registration_statement)

        self._mdiArea.addSubWindow(self._subwnd_major_report)
        self._subwnd_major_report.sig_open_document.connect(self.openDocument)
        self._subwnd_list.append(self._subwnd_major_report)

        self._mdiArea.addSubWindow(self._subwnd_financial_info)
        self._subwnd_financial_info.sig_open_document.connect(self.openDocument)
        self._subwnd_list.append(self._subwnd_financial_info)

        self._mdiArea.addSubWindow(self._subwnd_document_viewer)
        self._subwnd_list.append(self._subwnd_document_viewer)

        for wnd in self._subwnd_list:
            wnd.resize(600, 600)
            wnd.hide()
        self._mdiArea.cascadeSubWindows()

    def initMenuBar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        menuFile = QMenu('&File', menubar)
        menubar.addAction(menuFile.menuAction())
        menu_open_apikey_dlg = makeQAction(
            parent=self, text="OpenDART API Key 설정", triggered=self.openSetApiKeyDialog)
        menuFile.addAction(menu_open_apikey_dlg)
        menuFile.addSeparator()
        menu_close = makeQAction(parent=self, text="종료", triggered=self.close)
        menuFile.addAction(menu_close)

        menuView = QMenu('&View', menubar)
        menubar.addAction(menuView.menuAction())
        menuView.aboutToShow.connect(self.onMenuViewAboutToShow)

        for subwnd in self._subwnd_list:
            action = makeQAction(
                parent=self, text=subwnd.windowTitle(), checkable=True,
                triggered=partial(self.toggleSubWindowVisible, subwnd))
            self._menu_visible_subwnd_list.append((action, subwnd))
        self._menu_visible_subwnd_list.sort(key=lambda x: x[1].windowTitle())
        for elem in self._menu_visible_subwnd_list:
            action = elem[0]
            menuView.addAction(action)
        menuView.addSeparator()
        menu_close_all_subwnd = makeQAction(
            parent=self, text="모든 창 닫기", triggered=self._mdiArea.closeAllSubWindows)
        menuView.addAction(menu_close_all_subwnd)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj
        self._opendart.registerCallbackApiResponseException(self.onOpenDartApiResponseException)
        for subwnd in self._subwnd_list:
            if callable(getattr(subwnd, 'setOpenDartObject', None)):
                subwnd.setOpenDartObject(obj)

    def onOpenDartApiResponseException(self, status_code: int, message: str):
        QMessageBox.warning(self, 'API Response Exception', f'{status_code}: {message}')

    def openDocument(self, document_no: str):
        self._subwnd_document_viewer.showNormal()
        self._subwnd_document_viewer.show()
        self._subwnd_document_viewer.setDocumentNumber(document_no)

    def loadCompanyInformation(self, corp_code: str):
        self._subwnd_company_info.setCorporationCodeAndRefresh(corp_code)
        self._subwnd_business_report.setCorporationCode(corp_code)
        self._subwnd_share_disclosure.setCorporationCode(corp_code)
        self._subwnd_registration_statement.setCorporationCode(corp_code)
        self._subwnd_major_report.setCorporationCode(corp_code)
        self._subwnd_financial_info.setCorporationCode(corp_code)

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
        for elem in self._menu_visible_subwnd_list:
            action, subwnd = elem[0], elem[1]
            action.setChecked(subwnd.isVisible())

    def setCenterWindow(self):
        qtRect = self.frameGeometry()
        centerPt = QDesktopWidget().availableGeometry().center()
        qtRect.moveCenter(centerPt)
        self.move(qtRect.topLeft())

    def openSetApiKeyDialog(self):
        dlg = SetApiKeyDialog(self)
        dlg.setCurrentKey(self._opendart.getApiKey())
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
