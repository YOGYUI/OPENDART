# 증권신고서 주요정보 API 관련 UI
import os
import sys
import pandas as pd
from typing import List
from datetime import datetime
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QWidget, QComboBox, QLabel, QDateEdit
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart
from uiCommon import CommonReportWidget, CommonReportSubWindow


class RegistrationStatementWidget(CommonReportWidget):
    _df_result_list: List[pd.DataFrame]

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        self._type_func_list = [
            ('주식의 포괄적 교환·이전', 'getStockExchangeInfo'),
            ('합병', 'getMergeInfo'),
            ('증권예탁증권', 'getDepositaryReceiptInfo'),
            ('채무증권', 'getDebtSecuritiesInfo'),
            ('지분증권', 'getEquitySecuritiesInfo'),
            ('분할', 'getDivisionInfo')
        ]
        self._df_result_list = list()
        self._dateEditBegin = QDateEdit()
        self._dateEditEnd = QDateEdit()
        self._comboTitle = QComboBox()
        super().__init__(dart_obj=dart_obj, parent=parent)

    def initParameterLayout(self, vbox_gr: QVBoxLayout):
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('일자')
        lbl.setFixedWidth(50)
        hbox.addWidget(lbl)
        self._dateEditBegin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._dateEditBegin)
        lbl = QLabel('~')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._dateEditEnd.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._dateEditEnd)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('분류')
        lbl.setFixedWidth(50)
        hbox.addWidget(lbl)
        hbox.addWidget(self._comboTitle)
        vbox_gr.addWidget(subwgt)

    def initControl(self):
        self._cmbInfoType.currentIndexChanged.connect(self.onComboInfoTypeIndexChanged)
        super().initControl()
        self._dateEditEnd.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditEnd.setCalendarPopup(True)
        self._dateEditBegin.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditBegin.setCalendarPopup(True)
        date_end = datetime.now()
        self._dateEditEnd.setDate(QDate(date_end.year, date_end.month, date_end.day))
        self._dateEditBegin.setDate(QDate(date_end.year, 1, 1))
        self._comboTitle.currentIndexChanged.connect(self.onComboTitleIndexChanged)

    def search(self):
        if not self.checkValidity():
            return

        dateEnd = self._dateEditEnd.date().toString('yyyyMMdd')
        dateBegin = self._dateEditBegin.date().toString('yyyyMMdd')

        corp_code_list = self.getCorpCodeListFromEdit()
        index = self._cmbInfoType.currentIndex()
        func_name = self._type_func_list[index][1]
        method_to_call = getattr(self._opendart, func_name)

        self._df_result_list.clear()
        if len(corp_code_list) >= 1:
            # TODO: corp_code가 1개인 경우에만 동작하도록 구현됨
            code = corp_code_list[0]
            df_search_list = method_to_call(code, dateBegin, dateEnd)
            for df_search in df_search_list:
                df_result = pd.DataFrame()
                if df_result.empty:
                    for col in df_search.columns:
                        df_result[col] = None
                df_result = df_result.append(df_search, ignore_index=True)
                self._df_result_list.append(df_result)

        self.drawMultiTable()

    def onComboInfoTypeIndexChanged(self, index: int):
        func_name = self._type_func_list[index][1]
        method_to_get_titles = getattr(self._opendart, func_name + 'Titles')
        titles = method_to_get_titles()
        self._comboTitle.clear()
        self._comboTitle.addItems(titles)

    def onComboTitleIndexChanged(self):
        self.drawMultiTable()

    def drawMultiTable(self):
        index = self._comboTitle.currentIndex()
        if index >= 0:
            try:
                self.drawTable(self._df_result_list[index])
            except IndexError:
                pass
        else:
            self._tableResult.clearContents()
            self._tableResult.clear()


class RegistrationStatementSubWindow(CommonReportSubWindow):
    _widget: RegistrationStatementWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(dart_obj=dart_obj, parent=parent)
        self.setWindowTitle('증권신고서 주요정보')

    def initWidget(self, dart_obj: OpenDart = None):
        self._widget = RegistrationStatementWidget(dart_obj, self)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = RegistrationStatementSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
