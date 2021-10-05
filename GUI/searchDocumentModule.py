import os
import re
import sys
import pandas as pd
from typing import Union
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QMessageBox
from PyQt5.QtWidgets import QLineEdit, QPushButton, QCheckBox, QDateEdit, QLabel, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy, QHeaderView, QAbstractItemView
from PyQt5.QtWidgets import QMdiSubWindow
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart, Abbreviations
from uiCommon import ReadOnlyTableItem


class SearchDocumentWidget(QWidget):
    _opendart: Union[OpenDart, None] = None
    _df_search_result: pd.DataFrame = pd.DataFrame()

    sig_corporation_code = pyqtSignal(str)
    sig_open_document = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._editCompany = QLineEdit()
        self._tableSearchResult = QTableWidget()
        self._dateEditBegin = QDateEdit()
        self._dateEditEnd = QDateEdit()
        self._btnDate1week = QPushButton('1W')
        self._btnDate1month = QPushButton('1M')
        self._btnDate6month = QPushButton('6M')
        self._btnDate1year = QPushButton('1Y')
        self._btnDate3year = QPushButton('3Y')
        self._btnDate5year = QPushButton('5Y')
        self._btnDate10year = QPushButton('10Y')
        self._chkFinalReport = QCheckBox('Final Report')
        self._cmbCorpType = QComboBox()
        # TODO: Find, Clear Button
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        hbox.addWidget(self._editCompany)
        vbox.addWidget(subwgt)

        grbox = QGroupBox('Search Condition')
        vbox.addWidget(grbox)
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        vbox_gr = QVBoxLayout(grbox)
        vbox_gr.setContentsMargins(4, 6, 4, 4)
        vbox_gr.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('Duration')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._dateEditBegin.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._dateEditBegin)
        lbl = QLabel('~')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._dateEditEnd.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._dateEditEnd)
        btn_width = 36
        self._btnDate1week.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate1week.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate1week)
        self._btnDate1month.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate1month.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate1month)
        self._btnDate6month.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate6month.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate6month)
        self._btnDate1year.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate1year.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate1year)
        self._btnDate3year.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate3year.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate3year)
        self._btnDate5year.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate5year.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate5year)
        self._btnDate10year.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        self._btnDate10year.setFixedWidth(btn_width)
        hbox.addWidget(self._btnDate10year)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('Corporation Classification')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._cmbCorpType.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._cmbCorpType)
        self._chkFinalReport.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._chkFinalReport)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        vbox.addWidget(self._tableSearchResult)

    def initControl(self):
        self._editCompany.setPlaceholderText('Company Name / Company Unique Code (8 digit)')
        self._editCompany.returnPressed.connect(self.search)
        self._dateEditEnd.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditEnd.setCalendarPopup(True)
        self._dateEditBegin.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditBegin.setCalendarPopup(True)
        self.onClickBtnDateRange(timedelta(days=365))
        self._btnDate1week.clicked.connect(lambda: self.onClickBtnDateRange(timedelta(days=7)))
        self._btnDate1month.clicked.connect(lambda: self.onClickBtnDateRange(relativedelta(months=1)))
        self._btnDate6month.clicked.connect(lambda: self.onClickBtnDateRange(relativedelta(months=6)))
        self._btnDate1year.clicked.connect(lambda: self.onClickBtnDateRange(relativedelta(years=1)))
        self._btnDate3year.clicked.connect(lambda: self.onClickBtnDateRange(relativedelta(years=3)))
        self._btnDate5year.clicked.connect(lambda: self.onClickBtnDateRange(relativedelta(years=5)))
        self._btnDate10year.clicked.connect(lambda: self.onClickBtnDateRange(relativedelta(years=10)))
        self._chkFinalReport.setChecked(True)
        self._cmbCorpType.addItem('전체')
        self._cmbCorpType.addItems(Abbreviations.corp_cls.values())

        table_columns = ['공시대상회사', '보고서명', '제출인', '접수일자', '비고']
        self._tableSearchResult.setColumnCount(len(table_columns))
        self._tableSearchResult.setHorizontalHeaderLabels(table_columns)
        for i in [3, 4]:
            self._tableSearchResult.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._tableSearchResult.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._tableSearchResult.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tableSearchResult.itemDoubleClicked.connect(self.onTableSearchResultItemDoubleClicked)

    def search(self):
        self._tableSearchResult.clearContents()
        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return

        text = self._editCompany.text()
        if len(text) == 0:
            QMessageBox.warning(self, "Warning", "Invalid Corporation Name or Code")
            return

        regex = re.compile(r"^[0-9]{8}$")
        if regex.search(text) is not None:
            corp_code = [text]
        else:
            df_corp_filter = self._opendart.searchCorporationCodeWithName(text, match_exact=True)
            corp_code = list(df_corp_filter[df_corp_filter.columns[0]].values)

        df_result = pd.DataFrame()
        dateEnd = self._dateEditEnd.date().toString('yyyyMMdd')
        dateBegin = self._dateEditBegin.date().toString('yyyyMMdd')
        finalrpt = self._chkFinalReport.isChecked()
        idx = self._cmbCorpType.currentIndex()
        if idx == 0:
            corpClass = None
        else:
            corpClass = list(Abbreviations.corp_cls.keys())[idx - 1]

        for code in corp_code:
            df_search = self._opendart.searchDocument(
                corpCode=code, dateEnd=dateEnd, dateBegin=dateBegin, finalReport=finalrpt,
                corpClass=corpClass
            )
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self._df_search_result = df_result
        self.drawTable()

    def drawTable(self):
        rowcnt = len(self._df_search_result)
        df_result_values = self._df_search_result.values
        self._tableSearchResult.setRowCount(rowcnt)
        # corp_cls_text = {"Y": "유", "K": "코", "N": "넥", "E": "기"}
        for r in range(rowcnt):
            col = 0
            # 공시대상회사
            # corp_cls = corp_cls_text.get(df_result_values[r][0])
            # btn = QPushButton(corp_cls)
            corp_name = df_result_values[r][1]
            item = ReadOnlyTableItem(corp_name)
            item.setToolTip(corp_name)
            self._tableSearchResult.setItem(r, col, item)
            col += 1
            # 보고서명
            rpt_title = df_result_values[r][4]
            item = ReadOnlyTableItem(rpt_title)
            item.setToolTip(rpt_title)
            self._tableSearchResult.setItem(r, col, item)
            col += 1
            # 접수번호
            # item = ReadOnlyTableItem(df_result_values[r][5])
            # self._tableSearchResult.setItem(r, col, item)
            # col += 1
            # 제출인
            rpt_name = df_result_values[r][6]
            item = ReadOnlyTableItem(rpt_name)
            self._tableSearchResult.setItem(r, col, item)
            col += 1
            # 접수일자
            strdate = df_result_values[r][7]
            strdate = strdate[:4] + '.' + strdate[4:6] + '.' + strdate[6:]
            item = ReadOnlyTableItem(strdate)
            self._tableSearchResult.setItem(r, col, item)
            col += 1
            # 비고
            etc = df_result_values[r][8]
            item = ReadOnlyTableItem(etc)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            msg = ''
            rm_split = etc.split(' ')
            for e in rm_split:
                try:
                    msg += Abbreviations.search_doc_rm.get(e) + '\n'
                except Exception:
                    pass
            if len(msg) > 0:
                item.setToolTip(msg[:-1])
            self._tableSearchResult.setItem(r, col, item)
            col += 1

    def onClickBtnDateRange(self, td: Union[timedelta, relativedelta]):
        date_end = datetime.now()
        self._dateEditEnd.setDate(QDate(date_end.year, date_end.month, date_end.day))
        date_begin = (date_end - td)
        self._dateEditBegin.setDate(QDate(date_begin.year, date_begin.month, date_begin.day))

    def onTableSearchResultItemDoubleClicked(self, item: QTableWidgetItem):
        row = item.row()
        record = self._df_search_result.iloc[row]
        columns = self._df_search_result.columns
        corp_code = record[columns[0]]
        documnet_no = record[columns[5]]
        self.sig_corporation_code.emit(corp_code)
        self.sig_open_document.emit(documnet_no)


class SearchDocumentSubWindow(QMdiSubWindow):
    _widget: SearchDocumentWidget

    sig_corporation_code = pyqtSignal(str)
    sig_open_document = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widget = SearchDocumentWidget(dart_obj, self)
        self._widget.sig_corporation_code.connect(self.sig_corporation_code.emit)
        self._widget.sig_open_document.connect(self.sig_open_document.emit)
        self.setWidget(self._widget)
        self.setWindowTitle('Document Search')

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._widget.setOpenDartObject(obj)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = SearchDocumentSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
