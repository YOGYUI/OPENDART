import os
import sys
import pandas as pd
from typing import Union
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtGui import QShowEvent, QCloseEvent, QResizeEvent, QWheelEvent, QKeyEvent
from PyQt5.QtWidgets import QWidget, QMessageBox, QTableWidget, QTableWidgetItem, QScrollBar, QLineEdit, QPushButton
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QHeaderView, QAbstractItemView, QSizePolicy, QCheckBox
from PyQt5.QtWidgets import QMdiSubWindow, QApplication, QFileDialog
CURPATH = os.path.dirname(os.path.abspath(__file__))
GUIPATH = os.path.dirname(CURPATH)
PROJPATH = os.path.dirname(GUIPATH)
sys.path.extend([CURPATH, GUIPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, GUIPATH, PROJPATH
from opendart import OpenDart
from uiCommon import ReadOnlyTableItem


class CorporationListWidget(QWidget):
    _opendart: Union[OpenDart, None] = None
    _df_corp_list: pd.DataFrame = None
    _df_corp_list_display: pd.DataFrame = None
    _search_keyword: str = ''
    _search_index: int = 0
    _df_search: pd.DataFrame = None

    sig_corporation_code = pyqtSignal(str)
    sig_corporation_name = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._editSearch = QLineEdit()
        self._btnSearch = QPushButton('검색')
        self._btnSaveCsv = QPushButton('저장 (CSV)')
        self._table = QTableWidget()
        self._tableItemHeight = 30
        self._scrollVertical = QScrollBar()
        self._checkExactMatch = QCheckBox('일치')
        self._checkPublicMarketOnly = QCheckBox('상장회사만 표시')
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)
        self.refresh()

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(2, 0, 2, 0)
        hbox.addWidget(self._editSearch)
        self._btnSearch.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnSearch)
        self._btnSaveCsv.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnSaveCsv)
        self._checkExactMatch.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._checkExactMatch)
        vbox.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)
        hbox.addWidget(self._checkPublicMarketOnly)
        self._checkPublicMarketOnly.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(QWidget())
        vbox.addWidget(subwgt)

        subwgt = QWidget()
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)
        hbox.addWidget(self._table)
        hbox.addWidget(self._scrollVertical)
        vbox.addWidget(subwgt)

    def initControl(self):
        self._table.setSortingEnabled(False)
        styleSheet = "::section {background-color: #efefef;}"
        self._table.verticalHeader().setStyleSheet(styleSheet)
        self._table.horizontalHeader().setStyleSheet(styleSheet)
        self._table.setAlternatingRowColors(True)
        styleSheet = "QTableWidget {alternate-background-color: #eeeeee; background-color: white;}"
        self._table.setStyleSheet(styleSheet)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        columns = ['고유번호', '회사명', '종목코드', '최근변경일자']
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.itemDoubleClicked.connect(self.onTableItemDoubleClicked)

        self._scrollVertical.setOrientation(Qt.Vertical)
        self._scrollVertical.valueChanged.connect(self.onScrollVerticalValueChanged)
        self._scrollVertical.setMaximumWidth(18)

        self._editSearch.setPlaceholderText('Search Keyword: Corporation Name')
        self._editSearch.returnPressed.connect(self.search)
        self._btnSearch.clicked.connect(self.search)
        self._btnSearch.setIcon(QIcon('./Resource/find.png'))
        self._btnSaveCsv.clicked.connect(self.saveCsvFile)
        self._btnSaveCsv.setIcon(QIcon('./Resource/excel.png'))

        self._checkPublicMarketOnly.clicked.connect(self.onClickCheckMarketOnly)
        self._checkExactMatch.clicked.connect(self.onClickCheckExactMatch)

    def refresh(self):
        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return

        self._df_corp_list = self._opendart.loadCorporationDataFrame()
        if self._checkPublicMarketOnly.isChecked():
            self._df_corp_list_display = self._df_corp_list[self._df_corp_list['종목코드'].str.len() == 6]
            self._df_corp_list_display.reset_index(drop=True, inplace=True)
        else:
            self._df_corp_list_display = self._df_corp_list
        self.setVerticalScrollbarRange()
        self.drawTable()

    def onClickCheckMarketOnly(self):
        self._search_keyword = ''
        self.refresh()

    def onClickCheckExactMatch(self):
        self._search_keyword = ''

    def search(self):
        keyword = self._editSearch.text()
        if len(keyword) == 0:
            return
        if self._df_corp_list_display is None:
            return

        columns = self._df_corp_list_display.columns
        if self._search_keyword != keyword:
            self._search_keyword = keyword
            self._search_index = 0
            col = columns[1]
            if self._checkExactMatch.isChecked():
                self._df_search = self._df_corp_list_display[self._df_corp_list_display[col].str.fullmatch(keyword)]
            else:
                self._df_search = self._df_corp_list_display[self._df_corp_list_display[col].str.contains(keyword)]

        if len(self._df_search) > 0:
            index_list = self._df_search.index
            curoffset = self._scrollVertical.value()
            index_diff_list = [x - curoffset for x in index_list]
            if 0 in index_diff_list:
                index_diff_list.remove(0)
            index_diff_list = list(filter(lambda x: x > 0, index_diff_list))
            index_list = [x + curoffset for x in index_diff_list]
            if len(index_list) == 0:
                index = self._df_search.index[0]
            else:
                index = index_list[0]
            self.setVerticalOffset(index)
        else:
            QMessageBox.warning(self, "Warning", "Empty Result!")

    def saveCsvFile(self):
        if not self._df_corp_list.empty:
            options = QFileDialog.Options()
            path, _ = QFileDialog.getSaveFileName(self, 'Select File', 'result',
                                                  'Csv Format (*.csv)', options=options)
            if path:
                self._df_corp_list.to_csv(path, index=False)
        else:
            QMessageBox.warning(self, 'Warning', '파일 저장 불가 - 빈 테이블')

    def resizeEvent(self, a0: QResizeEvent) -> None:
        self.setTableItemLayout()
        self.setVerticalScrollbarRange()
        self.setVerticalHeaderLabels()
        self.drawTable()

    def setTableItemLayout(self):
        height = self._table.height()
        rowcnt = (height - self._table.horizontalHeader().height()) // self._tableItemHeight
        self._table.setRowCount(rowcnt)
        for r in range(self._table.rowCount()):
            self._table.setRowHeight(r, self._tableItemHeight)
            for c in range(self._table.columnCount()):
                item = ReadOnlyTableItem()
                self._table.setItem(r, c, item)
                if c in [0, 2, 3]:
                    item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

    def setVerticalScrollbarRange(self):
        if self._df_corp_list_display is not None:
            self._scrollVertical.setRange(0, len(self._df_corp_list_display) - self._table.rowCount())

    def setVerticalOffset(self, value: int):
        self._scrollVertical.setValue(value)
        self.drawTable()

    def drawTable(self):
        if self._df_corp_list_display is None or len(self._df_corp_list_display) == 0:
            return

        voffset = self._scrollVertical.value()
        for row in range(self._table.rowCount()):
            record = self._df_corp_list_display.iloc[row + voffset].values
            item = self._table.item(row, 0)
            item.setText(record[0])
            item = self._table.item(row, 1)
            item.setText(record[1])
            item = self._table.item(row, 2)
            item.setText(record[2])
            item = self._table.item(row, 3)
            item.setText(record[3].strftime('%Y-%m-%d'))

    def onScrollVerticalValueChanged(self):
        self.setVerticalHeaderLabels()
        self.drawTable()

    def setVerticalHeaderLabels(self):
        vlabels = [f'{x + self._scrollVertical.value() + 1}' for x in range(self._table.rowCount())]
        self._table.setVerticalHeaderLabels(vlabels)

    def wheelEvent(self, a0: QWheelEvent) -> None:
        delta_y = a0.angleDelta().y()
        offset = self._scrollVertical.value()
        if delta_y > 0:  # Wheel Up
            value = max(0, offset - 1)
            self.setVerticalOffset(value)
        elif delta_y < 0:  # Wheel Down
            if self._df_corp_list_display is not None:
                value = max(0, min(len(self._df_corp_list_display) - self._table.rowCount(), offset + 1))
                self.setVerticalOffset(value)

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        offset = self._scrollVertical.value()
        if a0.key() == Qt.Key_Up:
            value = max(0, offset - 1)
            self.setVerticalOffset(value)
        elif a0.key() == Qt.Key_Down:
            if self._df_corp_list_display is not None:
                value = max(0, min(len(self._df_corp_list_display) - self._table.rowCount(), offset + 1))
                self.setVerticalOffset(value)
        else:
            modifier = QApplication.keyboardModifiers()
            if modifier == Qt.ControlModifier:
                if a0.key() == Qt.Key_F:
                    self._editSearch.selectAll()
                    self._editSearch.setFocus()

    def onTableItemDoubleClicked(self, item: QTableWidgetItem):
        if self._df_corp_list_display is None or len(self._df_corp_list_display) == 0:
            return
        row = item.row() + self._scrollVertical.value()
        record = self._df_corp_list_display.iloc[row]
        columns = self._df_corp_list_display.columns
        corp_code = record[columns[0]]
        corp_name = record[columns[1]]
        self.sig_corporation_code.emit(corp_code)
        self.sig_corporation_name.emit(corp_name)


class CorporationListSubWindow(QMdiSubWindow):
    _widget: CorporationListWidget

    sig_corporation_code = pyqtSignal(str)
    sig_corporation_name = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widget = CorporationListWidget(dart_obj, self)
        self._widget.sig_corporation_code.connect(self.sig_corporation_code.emit)
        self._widget.sig_corporation_name.connect(self.sig_corporation_name.emit)
        self.setWidget(self._widget)
        self.setWindowTitle('기업 목록')

    def showEvent(self, showEvent: QShowEvent) -> None:
        self._widget.setTableItemLayout()
        self._widget.setVerticalScrollbarRange()
        self._widget.drawTable()

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._widget.setOpenDartObject(obj)


if __name__ == '__main__':
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wnd_ = CorporationListSubWindow(dart)
    wnd_.show()
    wnd_.resize(600, 600)

    app.exec_()
