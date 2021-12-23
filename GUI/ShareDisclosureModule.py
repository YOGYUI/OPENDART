# 지분공시 종합정보 API 관련 UI
import os
import re
import sys
import pandas as pd
from typing import Union
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QWidget, QTreeWidget, QTreeWidgetItem, QComboBox
from PyQt5.QtWidgets import QPushButton, QLineEdit, QLabel, QMessageBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy
from PyQt5.QtWidgets import QMdiSubWindow
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart
# TODO: Double-click - open document


type_func_list = [
    ('대량보유 상황보고', 'getMajorStockInformation'),
    ('임원ㆍ주요주주 소유보고', 'getExecutiveStockInformation'),
]


class ShareDisclosureWidget(QWidget):
    _opendart: Union[OpenDart, None] = None

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._editCompany = QLineEdit()
        self._cmbInfoType = QComboBox()
        self._btnSearch = QPushButton('SEARCH')
        self._tree = QTreeWidget()
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def initLayout(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(8)

        vbox.addWidget(self._editCompany)

        grbox = QGroupBox('Parameter')
        grbox.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        vbox_gr = QVBoxLayout(grbox)
        vbox_gr.setContentsMargins(4, 6, 4, 4)
        vbox_gr.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('Type')
        lbl.setFixedWidth(50)
        hbox.addWidget(lbl)
        hbox.addWidget(self._cmbInfoType)
        vbox_gr.addWidget(subwgt)

        vbox.addWidget(grbox)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        self._btnSearch.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnSearch)
        vbox.addWidget(subwgt)

        vbox.addWidget(self._tree)

    def initControl(self):
        self._editCompany.setPlaceholderText('Company Name / Company Unique Code (8 digit)')
        self._editCompany.returnPressed.connect(self.search)
        self._cmbInfoType.addItems([x[0] for x in type_func_list])
        self._btnSearch.clicked.connect(self.search)

        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(['Attribute', 'Value'])
        self._tree.setColumnWidth(0, 200)
        stylesheet = "QTreeView:item {border:0.5px; border-style:solid; "
        stylesheet += "border-color: lightgray; border-top: none; border-left: none}"
        stylesheet += "QTreeView:item:selected {background: #CDE8FF; selection-color: black}"
        self._tree.setStyleSheet(stylesheet)

    def search(self):
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
        index = self._cmbInfoType.currentIndex()
        func_name = type_func_list[index][1]
        method_to_call = getattr(self._opendart, func_name)
        for code in corp_code:
            df_search = method_to_call(code)
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self.drawTree(df_result)

    def drawTree(self, df: pd.DataFrame):
        # TODO: prettify
        self._tree.clear()
        columns = df.columns
        for r in range(len(df)):
            item = QTreeWidgetItem()
            item.setText(0, f'{r + 1}')
            self._tree.addTopLevelItem(item)
            for c in columns:
                subitem = QTreeWidgetItem()
                subitem.setText(0, c)
                subitem.setText(1, df.iloc[r][c])
                item.addChild(subitem)

    def setCorporationCode(self, corp_code: str):
        self._editCompany.setText(corp_code)


class ShareDisclosureSubWindow(QMdiSubWindow):
    _widget: ShareDisclosureWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widget = ShareDisclosureWidget(dart_obj, self)
        self.setWidget(self._widget)
        self.setWindowTitle('Share Disclosure')

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._widget.setOpenDartObject(obj)

    def setCorporationCode(self, corp_code: str):
        self._widget.setCorporationCode(corp_code)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = ShareDisclosureSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
