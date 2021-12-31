import os
import sys
import pandas as pd
from typing import Union
from datetime import datetime
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QDateEdit, QPushButton, QLabel, QRadioButton
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy, QMessageBox, QButtonGroup, QGroupBox
from PyQt5.QtWidgets import QHeaderView, QAbstractItemView
from PyQt5.QtWidgets import QMdiSubWindow
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart, Abbreviations
from uiCommon import ReadOnlyTableItem


class DailyDocumentWidget(QWidget):
    _opendart: Union[OpenDart, None] = None
    _df_daily_list: pd.DataFrame = pd.DataFrame()

    sig_corporation_code = pyqtSignal(str)
    sig_open_document = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._dateEditSearch = QDateEdit()
        self._btnRefresh = QPushButton('REFRESH')
        self._lblResult = QLabel()
        self._radioClassY = QRadioButton('유가증권')
        self._radioClassK = QRadioButton('코스닥')
        self._radioClassN = QRadioButton('코넥스')
        self._radioClassE = QRadioButton('기타법인')
        self._radioClassA = QRadioButton('전체')
        self._radioSortTime = QRadioButton('Time')
        self._radioSortCorpName = QRadioButton('Corporation Name')
        self._radioSortDocName = QRadioButton('Document Title')
        self._radioSortAscending = QRadioButton('Ascending')
        self._radioSortDescending = QRadioButton('Descending')
        self._table = QTableWidget()
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(8)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('Search Date')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._dateEditSearch.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._dateEditSearch)
        self._btnRefresh.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnRefresh)
        hbox.addWidget(self._lblResult)
        vbox.addWidget(subwgt)

        grbox = QGroupBox('Classification')
        grbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        vbox_gr = QVBoxLayout(grbox)
        vbox_gr.setContentsMargins(4, 6, 4, 4)
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        self._radioClassY.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioClassY)
        self._radioClassK.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioClassK)
        self._radioClassN.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioClassN)
        self._radioClassE.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioClassE)
        self._radioClassA.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioClassA)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)
        vbox.addWidget(grbox)

        grbox = QGroupBox('Sorting')
        grbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        vbox_gr = QVBoxLayout(grbox)
        vbox_gr.setContentsMargins(4, 6, 4, 4)
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        self._radioSortTime.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox.addWidget(self._radioSortTime)
        self._radioSortCorpName.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox.addWidget(self._radioSortCorpName)
        self._radioSortDocName.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox.addWidget(self._radioSortDocName)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 0, 0)
        hbox.setSpacing(4)
        self._radioSortAscending.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox.addWidget(self._radioSortAscending)
        self._radioSortDescending.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        hbox.addWidget(self._radioSortDescending)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)
        vbox.addWidget(grbox)

        vbox.addWidget(self._table)

    def initControl(self):
        self._dateEditSearch.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditSearch.setCalendarPopup(True)
        now = datetime.now()
        self._dateEditSearch.setDate(QDate(now.year, now.month, now.day))

        self._btnRefresh.clicked.connect(self.refresh)

        btngrp = QButtonGroup()
        btngrp.addButton(self._radioClassY)
        btngrp.addButton(self._radioClassK)
        btngrp.addButton(self._radioClassN)
        btngrp.addButton(self._radioClassE)
        btngrp.addButton(self._radioClassA)
        self._radioClassY.setChecked(True)

        btngrp = QButtonGroup()
        btngrp.addButton(self._radioSortTime)
        btngrp.addButton(self._radioSortCorpName)
        btngrp.addButton(self._radioSortDocName)
        self._radioSortTime.setChecked(True)
        self._radioSortTime.clicked.connect(self.drawTable)
        self._radioSortCorpName.clicked.connect(self.drawTable)
        self._radioSortDocName.clicked.connect(self.drawTable)

        btngrp = QButtonGroup()
        btngrp.addButton(self._radioSortAscending)
        btngrp.addButton(self._radioSortDescending)
        self._radioSortAscending.setChecked(True)
        self._radioSortAscending.clicked.connect(self.drawTable)
        self._radioSortDescending.clicked.connect(self.drawTable)

        table_columns = ['시간', '분류', '공시대상회사', '보고서명', '제출인', '접수일자', '비고']
        self._table.setColumnCount(len(table_columns))
        self._table.setHorizontalHeaderLabels(table_columns)
        for i in [0, 1, 5, 6]:
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.itemDoubleClicked.connect(self.onTableDailyListItemDoubleClicked)
        self._table.setAlternatingRowColors(True)
        styleSheet = "QTableWidget {alternate-background-color: #eeeeee; background-color: white;}"
        self._table.setStyleSheet(styleSheet)

    def refresh(self):
        self._lblResult.setText('')
        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return
        dateSearch = self._dateEditSearch.date().toString('yyyy.MM.dd')
        if self._radioClassY.isChecked():
            corpClass = 'Y'
        elif self._radioClassK.isChecked():
            corpClass = 'K'
        elif self._radioClassN.isChecked():
            corpClass = 'N'
        elif self._radioClassE.isChecked():
            corpClass = 'E'
        else:
            corpClass = None

        self._df_daily_list = self._opendart.getDailyUploadedDocuments(dateSearch, corpClass)
        msg = f'Total: {len(self._df_daily_list)}'
        self._lblResult.setText(msg)
        self.drawTable()

    def drawTable(self):
        self._table.setRowCount(0)
        rowcnt = len(self._df_daily_list)

        try:
            columns = self._df_daily_list.columns
            ascending = self._radioSortAscending.isChecked()
            if self._radioSortTime.isChecked():
                self._df_daily_list.sort_values(by=columns[0], ascending=ascending, inplace=True)
            elif self._radioSortCorpName.isChecked():
                self._df_daily_list.sort_values(by=columns[3], ascending=ascending, inplace=True)
            elif self._radioSortDocName.isChecked():
                self._df_daily_list.sort_values(by=columns[4], ascending=ascending, inplace=True)
        except Exception:
            pass

        df_list_values = self._df_daily_list.values
        self._table.setRowCount(rowcnt)
        for r in range(rowcnt):
            col = 0
            # 시간
            strtime = df_list_values[r][0]
            item = ReadOnlyTableItem(strtime)
            self._table.setItem(r, col, item)
            col += 1
            # 분류
            corp_class = df_list_values[r][2]
            item = ReadOnlyTableItem(corp_class[0])
            item.setToolTip(corp_class)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            self._table.setItem(r, col, item)
            col += 1
            # 공시대상회사
            corp_name = df_list_values[r][3]
            item = ReadOnlyTableItem(corp_name)
            item.setToolTip(corp_name)
            self._table.setItem(r, col, item)
            col += 1
            # 보고서명
            rpt_title = df_list_values[r][4]
            item = ReadOnlyTableItem(rpt_title)
            item.setToolTip(rpt_title)
            self._table.setItem(r, col, item)
            col += 1
            # 제출인
            rpt_name = df_list_values[r][6]
            item = ReadOnlyTableItem(rpt_name)
            item.setToolTip(rpt_name)
            self._table.setItem(r, col, item)
            col += 1
            # 접수일자
            strdate = df_list_values[r][7]
            item = ReadOnlyTableItem(strdate)
            self._table.setItem(r, col, item)
            col += 1
            # 비고
            etc = df_list_values[r][8]
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
            self._table.setItem(r, col, item)
            col += 1

    def onTableDailyListItemDoubleClicked(self, item: QTableWidgetItem):
        row = item.row()
        record = self._df_daily_list.iloc[row]
        columns = self._df_daily_list.columns
        corp_code = record[columns[1]]
        documnet_no = record[columns[5]]
        self.sig_corporation_code.emit(corp_code)
        self.sig_open_document.emit(documnet_no)


class DailyDocumentSubWindow(QMdiSubWindow):
    _widget: DailyDocumentWidget

    sig_corporation_code = pyqtSignal(str)
    sig_open_document = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widget = DailyDocumentWidget(dart_obj, self)
        self._widget.sig_corporation_code.connect(self.sig_corporation_code.emit)
        self._widget.sig_open_document.connect(self.sig_open_document.emit)
        self.setWidget(self._widget)
        self.setWindowTitle('일별 공시 문서 목록')

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
    wgt_ = DailyDocumentWidget(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
