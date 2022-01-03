import os
import re
import sys
import pandas as pd
from typing import Union
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QWidget, QMdiSubWindow, QTableWidget, QLineEdit, QLabel
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy, QHeaderView
CURPATH = os.path.dirname(os.path.abspath(__file__))
GUIPATH = os.path.dirname(CURPATH)
PROJPATH = os.path.dirname(GUIPATH)
sys.path.extend([CURPATH, GUIPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, GUIPATH, PROJPATH
from opendart import OpenDart, Abbreviations
from uiCommon import ReadOnlyTableItem


class CompanyInformationWidget(QWidget):
    _opendart: Union[OpenDart, None] = None
    _df_info: pd.DataFrame = pd.DataFrame()

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._editCorpCode = QLineEdit()
        self._table = QTableWidget()
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
        lbl = QLabel('고유번호/기업이름')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editCorpCode)
        vbox.addWidget(subwgt)

        vbox.addWidget(self._table)

    def initControl(self):
        self._editCorpCode.returnPressed.connect(self.getInformation)
        self._editCorpCode.setPlaceholderText('회사명 혹은 고유번호(8자리) 입력')
        # self._editCorpCode.setVisible(True)
        row_names = ['회사이름', '영문명', '공시회사명', '종목코드', '대표자명', '법인구분',
                     '법인등록번호', '사업자등록번호', '주소', '홈페이지', 'IR홈페이지',
                     '전화번호', '팩스번호', '업종명', '설립일', '결산월']
        self._table.setRowCount(len(row_names))
        self._table.setVerticalHeaderLabels(row_names)
        self._table.setColumnCount(1)
        self._table.horizontalHeader().hide()
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        stylesheet = "QTableWidget::item {padding: 10px;}"
        self._table.setStyleSheet(stylesheet)
        for r in range(self._table.rowCount()):
            item = ReadOnlyTableItem()
            self._table.setItem(r, 0, item)
        self._table.setAlternatingRowColors(True)
        styleSheet = "QTableWidget {alternate-background-color: #eeeeee; background-color: white;}"
        self._table.setStyleSheet(styleSheet)

    def setCorporationCodeAndRefresh(self, corp_code: str):
        self._editCorpCode.setText(corp_code)
        self.getInformation()

    def getInformation(self):
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 0)
            item.setText('')

        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return

        text = self._editCorpCode.text().strip()
        regex = re.compile(r"^[0-9]{8}$")
        if regex.search(text) is not None:
            corp_code = text
        else:
            df_corp_filter = self._opendart.searchCorporationCodeWithName(text, match_exact=True)
            corp_code_list = list(df_corp_filter[df_corp_filter.columns[0]].values)
            if len(corp_code_list) > 0:
                corp_code = corp_code_list[0]
            else:
                QMessageBox.warning(self, "Warning", "부적절한 회사명 혹은 고유번호")
                return

        self._df_info = self._opendart.getCompanyInformation(corp_code)
        self.drawTable()

    def drawTable(self):
        df_values = self._df_info.values
        row = 0
        try:
            # 회사이름
            corp_name = df_values[0][1]
            item = self._table.item(row, 0)
            item.setText(corp_name)
            row += 1
            # 영문명
            corp_name_eng = df_values[0][2]
            item = self._table.item(row, 0)
            item.setText(corp_name_eng)
            row += 1
            # 공시회사명
            corp_name_stock = df_values[0][3]
            item = self._table.item(row, 0)
            item.setText(corp_name_stock)
            row += 1
            # 종목코드
            stock_code = df_values[0][4]
            item = self._table.item(row, 0)
            item.setText(stock_code)
            row += 1
            # 대표자명
            exec_name = df_values[0][5]
            item = self._table.item(row, 0)
            item.setText(exec_name)
            row += 1
            # 법인구분
            corp_class = df_values[0][6]
            corp_class_name = Abbreviations.corp_cls.get(corp_class)
            item = self._table.item(row, 0)
            item.setText(corp_class_name)
            row += 1
            # 법인등록번호
            corp_reg_no = df_values[0][7]
            corp_reg_no = corp_reg_no[:6] + '-' + corp_reg_no[6:]
            item = self._table.item(row, 0)
            item.setText(corp_reg_no)
            row += 1
            # 사업자등록번호
            company_reg_no = df_values[0][8]
            company_reg_no = company_reg_no[:3] + '-' + company_reg_no[3:5] + '-' + company_reg_no[5:]
            item = self._table.item(row, 0)
            item.setText(company_reg_no)
            row += 1
            # 주소
            addr = df_values[0][9]
            item = self._table.item(row, 0)
            item.setText(addr)
            row += 1
            # 홈페이지
            homepage = df_values[0][10]
            item = self._table.item(row, 0)
            item.setText(homepage)
            row += 1
            # IR홈페이지
            ir_homepage = df_values[0][11]
            item = self._table.item(row, 0)
            item.setText(ir_homepage)
            row += 1
            # 전화번호
            phone_num = df_values[0][12]
            item = self._table.item(row, 0)
            item.setText(phone_num)
            row += 1
            # 팩스번호
            fax_num = df_values[0][13]
            item = self._table.item(row, 0)
            item.setText(fax_num)
            row += 1
            # 업종명
            sector = df_values[0][14]
            item = self._table.item(row, 0)
            item.setText(sector)
            row += 1
            # 설립일
            found_date = df_values[0][15]
            found_date = found_date[:4] + '-' + found_date[4:6] + '-' + found_date[6:]
            item = self._table.item(row, 0)
            item.setText(found_date)
            row += 1
            # 결산월
            settle_month = df_values[0][16] + '월'
            item = self._table.item(row, 0)
            item.setText(settle_month)
            row += 1
        except IndexError:
            pass

    def setCorporationCodeEditVisible(self, visible: bool):
        self._editCorpCode.setVisible(visible)

    def isCorporationCodeEditVisible(self) -> bool:
        return self._editCorpCode.isVisible()


class CompanyInformationSubWindow(QMdiSubWindow):
    _widget: CompanyInformationWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._widget = CompanyInformationWidget(dart_obj, self)
        self.setWidget(self._widget)
        self.setWindowTitle('기업 개황 정보')
        self.setFixedHeight(400)

    def closeEvent(self, closeEvent: QCloseEvent) -> None:
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._widget.setOpenDartObject(obj)

    def setCorporationCodeAndRefresh(self, corp_code: str):
        self._widget.setCorporationCodeAndRefresh(corp_code)

    def setCorporationCodeEditVisible(self, visible: bool):
        self._widget.setCorporationCodeEditVisible(visible)

    def isCorporationCodeEditVisible(self) -> bool:
        return self._widget.isCorporationCodeEditVisible()


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = CompanyInformationSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
