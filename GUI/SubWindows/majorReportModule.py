# 주요사항보고서 주요정보 API 관련 UI
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


class MajorReportWidget(CommonReportWidget):
    def __init__(self, dart_obj: OpenDart = None, parent=None):
        self._type_func_list = [
            ('부도발생', 'getBankruptcyOccurrenceInfo'),
            ('영업정지', 'getBusinessSuspensionInfo'),
            ('회생절차 개시신청', 'getRehabilitationProcedureInitiateInfo'),
            ('해산사유 발생', 'getDissolutionReasonOccurrenceInfo'),
            ('유상증자 결정', 'getRightsIssueDecisionInfo'),
            ('무상증자 결정', 'getBonusIssueDecisionInfo'),
            ('유무상증자 결정', 'getRightsBonusIssueDecisionInfo'),
            ('감자 결정', 'getCapitalReductionDecisionInfo'),
            ('채권은행 등의 관리절차 개시', 'getBankManagementProcedureInitiateInfo'),
            ('소송 등의 제기', 'getLitigationInfo'),
            ('해외 증권시장 주권등 상장 결정', 'getOverseasListingDecisionInfo'),
            ('해외 증권시장 주권등 상장폐지 결정', 'getOverseasDelistingDecisionInfo'),
            ('해외 증권시장 주권등 상장', 'getOverseasListingInfo'),
            ('해외 증권시장 주권등 상장폐지', 'getOverseasDelistingInfo'),
            ('전환사채권 발행결정', 'getConvertibleBondsPublishDecisionInfo'),
            ('신주인수권부사채권 발행결정', 'getBondWithWarrantPublishDecisionInfo'),
            ('교환사채권 발행결정', 'getExchangeableBondsPublishDecisionInfo'),
            ('채권은행 등의 관리절차 중단', 'getBankManagementProcedureStopInfo'),
            ('상각형 조건부자본증권 발행결정', 'getAmortizationContingentConvertibleBondPublishDecisionInfo'),
            ('자산양수도(기타), 풋백옵션', 'getAssetTransferPutbackOptionInfo'),
            ('타법인 주식 및 출자증권 양도결정', 'getOtherCorpStockEquitySecuritiesTransferDecisionInfo'),
            ('유형자산 양도 결정', 'getTangibleAssetsTransferDecisionInfo'),
            ('유형자산 양수 결정', 'getTangibleAssetsAcquisitionDecisionInfo'),
            ('타법인 주식 및 출자증권 양수결정', 'getOtherCorpStockEquitySecuritiesAcquisitionDecisionInfo'),
            ('영업양도 결정', 'getBusinessTransferDecisionInfo'),
            ('영업양수 결정', 'getBusinessAcquisitionDecisionInfo'),
            ('자기주식취득 신탁계약 해지 결정', 'getTreasuryStockAcqusitionTrustContractTerminationDecisionInfo'),
            ('자기주식취득 신탁계약 체결 결정', 'getTreasuryStockAcqusitionTrustContractConclusionDecisionInfo'),
            ('자기주식 처분 결정', 'getTreasuryStockDisposalDecisionInfo'),
            ('자기주식 취득 결정', 'getTreasuryStockAcquisitionDecisionInfo'),
            ('주식교환·이전 결정', 'getStockExchangeTransferDecisionInfo'),
            ('회사분할합병 결정', 'getCompanyDivisionMergeDecisionInfo'),
            ('회사분할 결정', 'getCompanyDivisionDecisionInfo'),
            ('회사합병 결정', 'getCompanyMergeDecisionInfo'),
            ('주권 관련 사채권 양수 결정', 'getDebenturesAcquisitionDecisionInfo'),
            ('주권 관련 사채권 양도 결정', 'getDebenturesTransferDecisionInfo')
        ]
        self._dateEditBegin = QDateEdit()
        self._dateEditEnd = QDateEdit()
        super().__init__(dart_obj=dart_obj, parent=parent)

    def initParameterLayout(self, vbox_gr: QVBoxLayout):
        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('Date')
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

    def initControl(self):
        super().initControl()
        self._dateEditEnd.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditEnd.setCalendarPopup(True)
        self._dateEditBegin.setDisplayFormat("yyyy.MM.dd ")
        self._dateEditBegin.setCalendarPopup(True)
        date_end = datetime.now()
        self._dateEditEnd.setDate(QDate(date_end.year, date_end.month, date_end.day))
        self._dateEditBegin.setDate(QDate(date_end.year, 1, 1))

    def search(self):
        if not self.checkValidity():
            return

        dateEnd = self._dateEditEnd.date().toString('yyyyMMdd')
        dateBegin = self._dateEditBegin.date().toString('yyyyMMdd')

        corp_code_list = self.getCorpCodeListFromEdit()
        index = self._cmbInfoType.currentIndex()
        func_name = self._type_func_list[index][1]
        method_to_call = getattr(self._opendart, func_name)
        df_result = pd.DataFrame()
        for code in corp_code_list:
            df_search = method_to_call(code, dateBegin, dateEnd)
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self.drawTable(df_result)


class MajorReportSubWindow(CommonReportSubWindow):
    _widget: MajorReportWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(dart_obj=dart_obj, parent=parent)
        self.setWindowTitle('주요사항보고서 주요정보')

    def initWidget(self, dart_obj: OpenDart = None):
        self._widget = MajorReportWidget(dart_obj, self)


if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wgt_ = MajorReportSubWindow(dart)
    wgt_.show()
    wgt_.resize(600, 600)

    app.exec_()
