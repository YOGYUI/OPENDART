# 상장기업 재무정보 API 관련 UI
import os
import sys
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QSpinBox, QRadioButton, QLabel, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart, ReportCode
from uiCommon import CommonReportWidget, CommonReportSubWindow


class FinanceInformationWidget(CommonReportWidget):
    def __init__(self, dart_obj: OpenDart = None, parent=None):
        self._type_func_list = [
            ('단일회사 주요계정', 'getSingleFinancialInformation'),
            ('다중회사 주요계정', 'getMultiFinancialInformation'),
            ('단일회사 전체 재무제표', 'getEntireFinancialStatements'),
            ('XBRL택사노미재무제표양식', 'getXbrlTaxonomyFormat'),
        ]
        self._spinYear = QSpinBox()
        self._radioRptCode1 = QRadioButton('1분기보고서')
        self._radioRptCode2 = QRadioButton('반기보고서')
        self._radioRptCode3 = QRadioButton('3분기보고서')
        self._radioRptCode4 = QRadioButton('사업보고서')
        self._radioDivCFS = QRadioButton('연결재무제표')
        self._radioDivOFS = QRadioButton('개별재무제표')
        self._comboSjDiv = QComboBox()
        super().__init__(dart_obj=dart_obj, parent=parent)

    def initParameterLayout(self, vbox_gr: QVBoxLayout):
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('연도')
        lbl.setFixedWidth(50)
        hbox.addWidget(lbl)
        self._spinYear.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._spinYear)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('종류')
        lbl.setFixedWidth(50)
        hbox.addWidget(lbl)
        self._radioRptCode1.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioRptCode1)
        self._radioRptCode2.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioRptCode2)
        self._radioRptCode3.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioRptCode3)
        self._radioRptCode4.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioRptCode4)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('개별/연결구분')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._radioDivOFS.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioDivOFS)
        self._radioDivCFS.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._radioDivCFS)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('재무제표구분')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._comboSjDiv)
        vbox_gr.addWidget(subwgt)

    def initControl(self):
        self._cmbInfoType.currentIndexChanged.connect(self.onComboInfoTypeIndexChanged)
        super().initControl()
        self._spinYear.setRange(2015, 9999)
        now = datetime.now()
        self._spinYear.setValue(now.year)
        self._radioRptCode1.setToolTip('11013')
        self._radioRptCode2.setToolTip('11012')
        self._radioRptCode3.setToolTip('11014')
        self._radioRptCode4.setToolTip('11011')
        self._radioRptCode4.setChecked(True)

        self._radioDivOFS.setChecked(True)
        self._radioDivOFS.setEnabled(False)
        self._radioDivCFS.setEnabled(False)
        self._comboSjDiv.setEnabled(False)

        self._comboSjDiv.addItems([
            'BS1 (재무상태표, 연결, 유동/비유동법)',
            'BS2 (재무상태표, 개별, 유동/비유동법)',
            'BS3 (재무상태표, 연결, 유동성배열법)',
            'BS4 (재무상태표, 개별, 유동성배열법)',
            'IS1 (별개의 손익계산서, 연결, 기능별분류)',
            'IS2 (별개의 손익계산서, 개별, 기능별분류)',
            'IS3 (별개의 손익계산서, 연결, 성격별분류)',
            'IS4 (별개의 손익계산서, 개별, 성격별분류)',
            'CIS1 (포괄손익계산서, 연결, 세후)',
            'CIS2 (포괄손익계산서, 개별, 세후)',
            'CIS3 (포괄손익계산서, 연결, 세전)',
            'CIS4 (포괄손익계산서, 개별, 세전)',
            'DCIS1 (단일 포괄손익계산서, 연결, 기능별분류, 세후포괄손익)',
            'DCIS2 (단일 포괄손익계산서, 개별, 기능별분류, 세후포괄손익)',
            'DCIS3 (단일 포괄손익계산서, 연결, 기능별분류, 세전)',
            'DCIS4 (단일 포괄손익계산서, 개별, 기능별분류, 세전)',
            'DCIS5 (단일 포괄손익계산서, 연결, 성격별분류, 세후포괄손익)',
            'DCIS6 (단일 포괄손익계산서, 개별, 성격별분류, 세후포괄손익)',
            'DCIS7 (단일 포괄손익계산서, 연결, 성격별분류, 세전)',
            'DCIS8 (단일 포괄손익계산서, 개별, 성격별분류, 세전)',
            'CF1 (현금흐름표, 연결, 직접법)',
            'CF2 (현금흐름표, 개별, 직접법)',
            'CF3 (현금흐름표, 연결, 간접법)',
            'CF4 (현금흐름표, 개별, 간접법)',
            'SCE1 (자본변동표, 연결)',
            'SCE2 (자본변동표, 개별)'
        ])

    def search(self):
        index = self._cmbInfoType.currentIndex()
        if index != 3:
            if not self.checkValidity():
                return

        year = self._spinYear.value()
        if self._radioRptCode1.isChecked():
            rptcode = ReportCode.FirstQuater
        elif self._radioRptCode2.isChecked():
            rptcode = ReportCode.HalfYear
        elif self._radioRptCode3.isChecked():
            rptcode = ReportCode.ThirdQuarter
        else:
            rptcode = ReportCode.Business

        if self._radioDivCFS.isChecked():
            fs_div = 'CFS'
        else:
            fs_div = 'OFS'

        sj_div = self._comboSjDiv.currentText().split('(')[0].strip()

        corp_code_list = self.getCorpCodeListFromEdit()
        func_name = self._type_func_list[index][1]
        method_to_call = getattr(self._opendart, func_name)
        df_result = pd.DataFrame()
        if index in [0, 1, 2]:
            for code in corp_code_list:
                if index in [0, 1]:
                    df_search = method_to_call(code, year, rptcode)
                    if df_result.empty:
                        for col in df_search.columns:
                            df_result[col] = None
                    df_result = df_result.append(df_search, ignore_index=True)
                elif index == 2:
                    df_search = method_to_call(code, year, rptcode, fs_div)
                    if df_result.empty:
                        for col in df_search.columns:
                            df_result[col] = None
                    df_result = df_result.append(df_search, ignore_index=True)
        elif index == 3:
            df_search = method_to_call(sj_div)
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self.drawTable(df_result)

    def onComboInfoTypeIndexChanged(self, index: int):
        self._spinYear.setEnabled(index in [0, 1, 2])
        self._radioRptCode1.setEnabled(index in [0, 1, 2])
        self._radioRptCode2.setEnabled(index in [0, 1, 2])
        self._radioRptCode3.setEnabled(index in [0, 1, 2])
        self._radioRptCode4.setEnabled(index in [0, 1, 2])
        self._radioDivCFS.setEnabled(index == 2)
        self._radioDivOFS.setEnabled(index == 2)
        self._comboSjDiv.setEnabled(index == 3)


class FinanceInformationSubWindow(CommonReportSubWindow):
    _widget: FinanceInformationWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(dart_obj=dart_obj, parent=parent)
        self.setWindowTitle('상장기업 재무정보')

    def initWidget(self, dart_obj: OpenDart = None):
        self._widget = FinanceInformationWidget(dart_obj, self)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = FinanceInformationSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
