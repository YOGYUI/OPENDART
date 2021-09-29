import os
import re
import sys
import pandas as pd
from datetime import datetime, timedelta
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import QWidget, QTableWidget, QTableWidgetItem
from PyQt5.QtWidgets import QLineEdit, QPushButton, QCheckBox, QDateEdit, QLabel
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy, QHeaderView
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart


class SearchDocumentWidget(QWidget):
    _opendart: OpenDart

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._editCompany = QLineEdit()
        self._tableSearchResult = QTableWidget()
        self._dateEditBegin = QDateEdit()
        self._dateEditEnd = QDateEdit()
        self.initControl()
        self.initLayout()

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        hbox.addWidget(self._editCompany)
        vbox.addWidget(subwgt)

        grbox = QGroupBox('Condition')
        vbox.addWidget(grbox)
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        vbox_gr = QVBoxLayout(grbox)
        vbox_gr.setContentsMargins(4, 4, 4, 4)
        vbox_gr.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('Duration')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._dateEditBegin)
        lbl = QLabel('~')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._dateEditEnd)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        vbox.addWidget(self._tableSearchResult)

    def initControl(self):
        self._editCompany.setPlaceholderText('Company Name / Company Unique Code (8 digit)')
        self._editCompany.returnPressed.connect(self.search)
        date_end = datetime.now()
        self._dateEditEnd.setDate(QDate(date_end.year, date_end.month, date_end.day))
        date_begin = (date_end - timedelta(days=365))
        self._dateEditBegin.setDate(QDate(date_begin.year, date_begin.month, date_begin.day))

        table_columns = ['공시대상회사', '보고서명', '접수번호', '제출인', '접수일자', '비고']
        self._tableSearchResult.setColumnCount(len(table_columns))
        self._tableSearchResult.setHorizontalHeaderLabels(table_columns)
        for i in [2, 4, 5]:
            self._tableSearchResult.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._tableSearchResult.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def search(self):
        text = self._editCompany.text()
        regex = re.compile(r"^[0-9]{8}$")
        if regex.search(text) is not None:
            corp_code = [text]
        else:
            df_corp_filter = self._opendart.searchCorporationCodeWithName(text, match_exact=True)
            corp_code = list(df_corp_filter[df_corp_filter.columns[0]].values)

        df_result = pd.DataFrame()
        dateEnd = self._dateEditEnd.date().toString('yyyyMMdd')
        dateBegin = self._dateEditBegin.date().toString('yyyyMMdd')

        for code in corp_code:
            df_search = self._opendart.searchDocument(
                corpCode=code, dateEnd=dateEnd, dateBegin=dateBegin
            )
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self.drawTableSearchResult(df_result)

    def drawTableSearchResult(self, df_result: pd.DataFrame):
        self._tableSearchResult.clearContents()
        rowcnt = len(df_result)
        df_result_values = df_result.values
        self._tableSearchResult.setRowCount(rowcnt)
        for r in range(rowcnt):
            item = QTableWidgetItem(df_result_values[r][1])
            self._tableSearchResult.setItem(r, 0, item)

            item = QTableWidgetItem(df_result_values[r][4])
            self._tableSearchResult.setItem(r, 1, item)

            item = QTableWidgetItem(df_result_values[r][5])
            self._tableSearchResult.setItem(r, 2, item)

            item = QTableWidgetItem(df_result_values[r][6])
            self._tableSearchResult.setItem(r, 3, item)

            item = QTableWidgetItem(df_result_values[r][7])
            self._tableSearchResult.setItem(r, 4, item)

            item = QTableWidgetItem(df_result_values[r][8])
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._tableSearchResult.setItem(r, 5, item)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = SearchDocumentWidget()
    wgt_.setOpenDartObject(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()

