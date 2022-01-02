# 사업보고서 주요정보 API 관련 UI
import os
import sys
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QSpinBox, QRadioButton, QLabel
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy
CURPATH = os.path.dirname(os.path.abspath(__file__))
PROJPATH = os.path.dirname(CURPATH)
sys.path.extend([CURPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, PROJPATH
from opendart import OpenDart, ReportCode
from uiCommon import CommonReportWidget, CommonReportSubWindow


class BusinessReportWidget(CommonReportWidget):
    def __init__(self, dart_obj: OpenDart = None, parent=None):
        self._type_func_list = [
            ('조건부 자본증권 미상환 잔액', 'getContingentConvertibleBondOutstandingBalanceInfo'),
            ('미등기임원 보수현황', 'getUnregisteredOfficerRemunerationInfo'),
            ('회사채 미상환 잔액', 'getDebentureOutstandingBalanceInfo'),
            ('단기사채 미상환 잔액', 'getShortTermBondOutstandingBalanceInfo'),
            ('기업어음증권 미상환 잔액', 'getPaperSecuritiesOutstandingBalanceInfo'),
            ('채무증권 발행실적', 'getDebtSecuritiesPublishInfo'),
            ('사모자금의 사용내역', 'getPrivateCapitalUsageDetailInfo'),
            ('공모자금의 사용내역', 'getPublicCapitalUsageDetailInfo'),
            ('이사·감사 전체의 보수현황(주주총회 승인금액)', 'getEntireOfficerRemunerationByApprovalInfo'),
            ('이사·감사 전체의 보수현황(보수지급금액 - 유형별)', 'getEntireOfficerRemunerationByPaymentsInfo'),
            ('주식의 총수 현황', 'getStockTotalQuantityInfo'),
            ('회계감사인의 명칭 및 감사의견', 'getAccountingAuditorAndOpinionInfo'),
            ('감사용역체결현황', 'getAuditServiceContractStatusInfo'),
            ('회계감사인과의 비감사용역 계약체결 현황', 'getNonAuditServiceContractStatusInfo'),
            ('사외이사 및 그 변동현황', 'getOutsideDirectorAndChangeStatusInfo'),
            ('신종자본증권 미상환 잔액', 'getHybridSecuritiesOutstandingBalanceInfo'),
            ('증자(감자) 현황', 'getCapitalIncreaseDecreaseStatusInfo'),
            ('배당에 관한 사항', 'getDividendDetailInfo'),
            ('자기주식 취득 및 처분 현황', 'getTreasuryStockAcquisitionDisposalInfo'),
            ('최대주주 현황', 'getMajorityShareholderStatusInfo'),
            ('최대주주 변동현황', 'getMajorityShareholderChangeStatusInfo'),
            ('소액주주 현황', 'getMinorityShareholderStatusInfo'),
            ('임원 현황', 'getExecutivesStatusInfo'),
            ('직원 현황', 'getEmployeeStatusInfo'),
            ('이사·감사의 개인별 보수 현황', 'getIndivisualOfficerRemunerationStatusInfo'),
            ('이사·감사 전체의 보수현황', 'getEntireOfficerRemunerationStatusInfo'),
            ('개인별 보수지급 금액(5억이상 상위5인)', 'getHighestIndivisualRemunerationInfo'),
            ('타법인 출자현황', 'getOtherCorporationInvestmentStatusInfo'),
        ]
        self._spinYear = QSpinBox()
        self._radioRptCode1 = QRadioButton('1분기보고서')
        self._radioRptCode2 = QRadioButton('반기보고서')
        self._radioRptCode3 = QRadioButton('3분기보고서')
        self._radioRptCode4 = QRadioButton('사업보고서')
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

    def initControl(self):
        super().initControl()
        self._spinYear.setRange(2015, 9999)
        now = datetime.now()
        self._spinYear.setValue(now.year)
        self._radioRptCode1.setToolTip('11013')
        self._radioRptCode2.setToolTip('11012')
        self._radioRptCode3.setToolTip('11014')
        self._radioRptCode4.setToolTip('11011')
        self._radioRptCode4.setChecked(True)

    def search(self):
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

        corp_code_list = self.getCorpCodeListFromEdit()
        index = self._cmbInfoType.currentIndex()
        func_name = self._type_func_list[index][1]
        method_to_call = getattr(self._opendart, func_name)
        df_result = pd.DataFrame()
        for code in corp_code_list:
            df_search = method_to_call(code, year, rptcode)
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self.drawTable(df_result)


class BusinessReportSubWindow(CommonReportSubWindow):
    _widget: BusinessReportWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(dart_obj=dart_obj, parent=parent)
        self.setWindowTitle('사업보고서 주요정보')

    def initWidget(self, dart_obj: OpenDart = None):
        self._widget = BusinessReportWidget(dart_obj, self)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = BusinessReportSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
