import os
import re
import sys
import pandas as pd
from collections import OrderedDict
from typing import Union, List, Tuple
from abc import abstractmethod
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QCloseEvent
from PyQt5.QtWidgets import QWidget, QMdiSubWindow, QTableWidget, QTableWidgetItem, QAction
from PyQt5.QtWidgets import QPushButton, QLineEdit, QComboBox, QMessageBox, QLabel, QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy, QAbstractItemView
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart


class ReadOnlyTableItem(QTableWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(Qt.ItemFlags(int(self.flags()) ^ Qt.ItemIsEditable))


def makeQAction(**kwargs):
    parent = kwargs.get('parent')
    text = kwargs.get('text')
    iconPath = kwargs.get('iconPath')
    triggered = kwargs.get('triggered')
    checkable = kwargs.get('checkable', False)
    checked = kwargs.get('checked', False)

    action = QAction(parent)
    action.setText(text)
    action.setIcon(QIcon(iconPath))
    if triggered is not None:
        action.triggered.connect(triggered)
    action.setCheckable(checkable)
    action.setChecked(checked)

    return action


def getDataFrameFromTableWidget(table: QTableWidget) -> pd.DataFrame:
    try:
        hlabels = [table.horizontalHeaderItem(x).text() for x in range(table.columnCount())]
        record_list = list()
        for row in range(table.rowCount()):
            record = OrderedDict()
            for col in range(table.columnCount()):
                record[hlabels[col]] = table.item(row, col).text()
            record_list.append(record)
        df = pd.DataFrame(record_list)
        df.columns = hlabels
    except Exception:
        df = pd.DataFrame()
    return df


class CommonReportWidget(QWidget):
    _opendart: Union[OpenDart, None] = None
    _type_func_list: List[Tuple[str, str]]
    _doc_no_col_index: int = -1

    sig_open_document = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self.setOpenDartObject(dart_obj)
        self._editCompany = QLineEdit()
        self._cmbInfoType = QComboBox()
        self._btnSearch = QPushButton('검색')
        self._btnSaveCsv = QPushButton('저장 (CSV)')
        self._btnClear = QPushButton('초기화')
        self._tableResult = QTableWidget()
        self.initControl()
        self.initLayout()

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(8)

        vbox.addWidget(self._editCompany)

        grbox = QGroupBox('검색 조건')
        grbox.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        vbox_gr = QVBoxLayout(grbox)
        vbox_gr.setContentsMargins(4, 6, 4, 4)
        vbox_gr.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('유형')
        lbl.setFixedWidth(50)
        hbox.addWidget(lbl)
        hbox.addWidget(self._cmbInfoType)
        vbox_gr.addWidget(subwgt)
        self.initParameterLayout(vbox_gr)
        vbox.addWidget(grbox)

        self.initButtonLayout(vbox)
        vbox.addWidget(self._tableResult)

    def initParameterLayout(self, vbox_gr: QVBoxLayout):
        pass

    def initButtonLayout(self, vbox: QVBoxLayout):
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        hbox.addWidget(QWidget())
        self._btnSearch.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnSearch)
        self._btnSaveCsv.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnSaveCsv)
        self._btnClear.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnClear)
        hbox.addWidget(QWidget())
        vbox.addWidget(subwgt)

    def initControl(self):
        self._editCompany.setPlaceholderText('회사명 혹은 고유번호(8자리) 입력')
        self._editCompany.returnPressed.connect(self.search)
        self._cmbInfoType.addItems([x[0] for x in self._type_func_list])
        self._btnSearch.clicked.connect(self.search)
        self._btnSearch.setIcon(QIcon('./Resource/find.png'))
        self._btnSaveCsv.clicked.connect(self.saveCsvFile)
        self._btnSaveCsv.setIcon(QIcon('./Resource/excel.png'))
        self._btnClear.clicked.connect(self.clear)
        self._btnClear.setIcon(QIcon('./Resource/clear.png'))

        self._tableResult.verticalHeader().hide()
        self._tableResult.setAlternatingRowColors(True)
        self._tableResult.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tableResult.itemDoubleClicked.connect(self.onTableResultItemDoubleClicked)
        styleSheet = "QTableWidget {alternate-background-color: #eeeeee; background-color: white;}"
        self._tableResult.setStyleSheet(styleSheet)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def setCorporationCode(self, corp_code: str):
        self._editCompany.setText(corp_code)

    def setCorporationName(self, name: str):
        self._editCompany.setText(name)

    @abstractmethod
    def search(self):
        pass

    def clear(self):
        self._editCompany.setText('')
        self._tableResult.clearContents()
        self._tableResult.clear()
        self._tableResult.setRowCount(0)
        self._tableResult.setColumnCount(0)

    def saveCsvFile(self):
        df = getDataFrameFromTableWidget(self._tableResult)
        if not df.empty:
            options = QFileDialog.Options()
            path, _ = QFileDialog.getSaveFileName(self, 'Select File', 'result',
                                                  'Csv Format (*.csv)', options=options)
            if path:
                df.to_csv(path, index=False)
        else:
            QMessageBox.warning(self, 'Warning', '파일 저장 불가 - 빈 테이블')

    def checkValidity(self) -> bool:
        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return False
        text = self._editCompany.text()
        if len(text) == 0:
            QMessageBox.warning(self, "Warning", "부적절한 회사명 혹은 고유번호")
            return False
        return True

    def getCorpCodeListFromEdit(self) -> List[str]:
        text = self._editCompany.text().strip()
        regex = re.compile(r"^[0-9]{8}$")
        if regex.search(text) is not None:
            corp_code_list = [text]
        else:
            df_corp_filter = self._opendart.searchCorporationCodeWithName(text, match_exact=True)
            corp_code_list = list(df_corp_filter[df_corp_filter.columns[0]].values)
        return corp_code_list

    def drawTable(self, df: pd.DataFrame):
        self._tableResult.clearContents()
        self._tableResult.clear()

        columns = df.columns
        self._tableResult.setColumnCount(len(columns))
        self._tableResult.setHorizontalHeaderLabels(columns)
        self._tableResult.setRowCount(len(df))
        values = df.values
        for row in range(self._tableResult.rowCount()):
            for col in range(self._tableResult.columnCount()):
                item_text = str(values[row, col])
                item = ReadOnlyTableItem(item_text)
                item.setToolTip(item_text)
                self._tableResult.setItem(row, col, item)
        self._doc_no_col_index = list(columns).index('접수번호') if '접수번호' in columns else -1

    def onTableResultItemDoubleClicked(self, item: QTableWidgetItem):
        if self._doc_no_col_index < 0:
            return
        row = item.row()
        text = self._tableResult.item(row, self._doc_no_col_index).text()
        self.sig_open_document.emit(text)


class CommonReportSubWindow(QMdiSubWindow):
    _widget: CommonReportWidget = None

    sig_open_document = pyqtSignal(str)

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self.initWidget(dart_obj)
        if self._widget is not None:
            self.setWidget(self._widget)
            self._widget.sig_open_document.connect(self.sig_open_document.emit)

    @abstractmethod
    def initWidget(self, dart_obj: OpenDart = None):
        pass

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._widget.setOpenDartObject(obj)

    def setCorporationCode(self, corp_code: str):
        self._widget.setCorporationCode(corp_code)

    def setCorporationName(self, name: str):
        self._widget.setCorporationName(name)
