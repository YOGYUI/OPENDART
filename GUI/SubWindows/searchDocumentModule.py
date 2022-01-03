import os
import re
import sys
import pandas as pd
from typing import Union
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import QWidget, QTableWidgetItem, QMessageBox
from PyQt5.QtWidgets import QPushButton, QCheckBox, QDateEdit, QLabel, QComboBox
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy, QHeaderView, QFileDialog
CURPATH = os.path.dirname(os.path.abspath(__file__))
GUIPATH = os.path.dirname(CURPATH)
PROJPATH = os.path.dirname(GUIPATH)
sys.path.extend([CURPATH, GUIPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, GUIPATH, PROJPATH
from opendart import OpenDart, Abbreviations
from uiCommon import CommonReportWidget, CommonReportSubWindow, ReadOnlyTableItem


class SearchDocumentWidget(CommonReportWidget):
    _df_search_result: pd.DataFrame = pd.DataFrame()

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        self._type_func_list = []
        self._dateEditBegin = QDateEdit()
        self._dateEditEnd = QDateEdit()
        self._btnDate1week = QPushButton('1주일')
        self._btnDate1month = QPushButton('1개월')
        self._btnDate6month = QPushButton('6개월')
        self._btnDate1year = QPushButton('1년')
        self._btnDate3year = QPushButton('3년')
        self._btnDate5year = QPushButton('5년')
        self._btnDate10year = QPushButton('10년')
        self._chkFinalReport = QCheckBox('최종보고서')
        self._cmbCorpType = QComboBox()
        self._cmbPublishType = QComboBox()
        self._cmbPublishDetail = QComboBox()
        super().__init__(dart_obj=dart_obj, parent=parent)

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

        grbox = QGroupBox('검색 조건')
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
        lbl = QLabel('기간')
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
        lbl = QLabel('법인 유형')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._cmbCorpType.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._cmbCorpType)
        self._chkFinalReport.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._chkFinalReport)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('공시 유형')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        self._cmbPublishType.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._cmbPublishType)
        lbl = QLabel('상세')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        # self._cmbPublishDetail.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._cmbPublishDetail)
        hbox.addWidget(QWidget())
        vbox_gr.addWidget(subwgt)

        self.initButtonLayout(vbox)
        vbox.addWidget(self._tableResult)

    def initControl(self):
        super().initControl()
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
        self._cmbPublishType.addItems([
            '전체', '정기공시', '주요사항보고', '발행공시', '지분공시', '기타공시',
            '외부감사관련', '펀드공시', '자산유동화', '거래소공시', '공정위공시'
        ])
        self._cmbPublishType.currentIndexChanged.connect(self.onComboPublishTypeIndexChanged)
        self._cmbPublishDetail.setEnabled(False)

        table_columns = ['공시대상회사', '보고서명', '제출인', '접수일자', '비고']
        self._tableResult.verticalHeader().show()
        self._tableResult.setColumnCount(len(table_columns))
        self._tableResult.setHorizontalHeaderLabels(table_columns)
        for i in [3, 4]:
            self._tableResult.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self._tableResult.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)

    def search(self):
        self._tableResult.clearContents()
        if self._opendart is None:
            QMessageBox.warning(self, "Warning", "Open DART object is None!")
            return

        text = self._editCompany.text()
        if len(text) == 0:
            QMessageBox.warning(self, "Warning", "부적절한 회사명 혹은 고유번호")
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
        idx = self._cmbPublishType.currentIndex()
        if idx == 0:
            pbType = None
            pbTypeDetail = None
        else:
            pbType = chr(idx - 1 + ord('A'))
            idx2 = self._cmbPublishDetail.currentIndex()
            if idx2 == 0:
                pbTypeDetail = None
            else:
                pbTypeDetail = pbType + '{:03d}'.format(idx2)
                pbType = None

        for code in corp_code:
            df_search = self._opendart.searchDocument(
                corpCode=code,
                dateEnd=dateEnd,
                dateBegin=dateBegin,
                finalReport=finalrpt,
                pbType=pbType,
                pbTypeDetail=pbTypeDetail,
                corpClass=corpClass
            )
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self._df_search_result = df_result
        self.drawTable(self._df_search_result)

    def clear(self):
        self._editCompany.setText('')
        self._tableResult.clearContents()
        self._tableResult.setRowCount(0)

    def saveCsvFile(self):
        if not self._df_search_result.empty:
            options = QFileDialog.Options()
            path, _ = QFileDialog.getSaveFileName(self, 'Select File', 'result',
                                                  'Csv Format (*.csv)', options=options)
            if path:
                self._df_search_result.to_csv(path, index=False)
        else:
            QMessageBox.warning(self, 'Warning', '파일 저장 불가 - 빈 테이블')

    def drawTable(self, df: pd.DataFrame):
        rowcnt = len(df)
        df_result_values = df.values
        self._tableResult.setRowCount(rowcnt)
        if rowcnt == 0:
            # QMessageBox.warning(self, "Warning", "Empty Result!")
            return

        # corp_cls_text = {"Y": "유", "K": "코", "N": "넥", "E": "기"}
        for r in range(rowcnt):
            col = 0
            # 공시대상회사
            # corp_cls = corp_cls_text.get(df_result_values[r][0])
            # btn = QPushButton(corp_cls)
            corp_name = df_result_values[r][1]
            item = ReadOnlyTableItem(corp_name)
            item.setToolTip(corp_name)
            self._tableResult.setItem(r, col, item)
            col += 1
            # 보고서명
            rpt_title = df_result_values[r][4]
            item = ReadOnlyTableItem(rpt_title)
            item.setToolTip(rpt_title)
            self._tableResult.setItem(r, col, item)
            col += 1
            # 접수번호
            # item = ReadOnlyTableItem(df_result_values[r][5])
            # self._tableResult.setItem(r, col, item)
            # col += 1
            # 제출인
            rpt_name = df_result_values[r][6]
            item = ReadOnlyTableItem(rpt_name)
            self._tableResult.setItem(r, col, item)
            col += 1
            # 접수일자
            strdate = df_result_values[r][7]
            strdate = strdate[:4] + '.' + strdate[4:6] + '.' + strdate[6:]
            item = ReadOnlyTableItem(strdate)
            self._tableResult.setItem(r, col, item)
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
            self._tableResult.setItem(r, col, item)
            col += 1

    def onClickBtnDateRange(self, td: Union[timedelta, relativedelta]):
        date_end = datetime.now()
        self._dateEditEnd.setDate(QDate(date_end.year, date_end.month, date_end.day))
        date_begin = (date_end - td)
        self._dateEditBegin.setDate(QDate(date_begin.year, date_begin.month, date_begin.day))

    def onTableResultItemDoubleClicked(self, item: QTableWidgetItem):
        row = item.row()
        record = self._df_search_result.iloc[row]
        columns = self._df_search_result.columns
        # corp_code = record[columns[0]]
        documnet_no = record[columns[5]]
        self.sig_open_document.emit(documnet_no)

    def onComboPublishTypeIndexChanged(self, index: int):
        self._cmbPublishDetail.clear()
        if index == 0:
            self._cmbPublishDetail.setEnabled(False)
        else:
            self._cmbPublishDetail.setEnabled(True)
            if index == 1:  # A: 정기공시
                self._cmbPublishDetail.addItems([
                    '전체', '사업보고서', '반기보고서', '분기보고서',
                    '등록법인결산서류(자본시장법 이전)', '소액공모법인결산서류'
                ])
            elif index == 2:  # B: 주요사항보고
                self._cmbPublishDetail.addItems([
                    '전체', '주요사항보고서', '주요경영사항신고(자본시장법 이전)',
                    '최대주주등과의거래신고(자본시장법 이전)'
                ])
            elif index == 3:  # C: 발행공시
                self._cmbPublishDetail.addItems([
                    '전체', '증권신고(지분증권)', '증권신고(채무증권)', '증권신고(파생결합증권)', '증권신고(합병등)',
                    '증권신고(기타)', '소액공모(지분증권)', '소액공모(채무증권)', '소액공모(파생결합증권)',
                    '소액공모(합병등)', '소액공모(기타)', '호가중개시스템을통한소액매출'
                ])
            elif index == 4:  # D: 지분공시
                self._cmbPublishDetail.addItems([
                    '전체', '주식등의대량보유상황보고서', '임원ㆍ주요주주특정증권등소유상황보고서',
                    '의결권대리행사권유', '공개매수'
                ])
            elif index == 5:  # E: 기타공시
                self._cmbPublishDetail.addItems([
                    '전체', '자기주식취득/처분"', '신탁계약체결/해지', '합병등종료보고서',
                    '주식매수선택권부여에관한신고', '사외이사에관한신고', '주주총회소집공고', '시장조성/안정조작',
                    '합병등신고서(자본시장법 이전)', '금융위등록/취소(자본시장법 이전)'
                ])
            elif index == 6:  # F: 외부감사관련
                self._cmbPublishDetail.addItems([
                    '전체', '감사보고서', '연결감사보고서', '결합감사보고서', '회계법인사업보고서',
                    '감사전재무제표미제출신고서'
                ])
            elif index == 7:  # G: 펀드공시
                self._cmbPublishDetail.addItems([
                    '전체', '증권신고(집합투자증권-신탁형)', '증권신고(집합투자증권-회사형)',
                    '증권신고(집합투자증권-합병)'
                ])
            elif index == 8:  # H: 자산유동화
                self._cmbPublishDetail.addItems([
                    '전체', '자산유동화계획/양도등록', '사업/반기/분기보고서', '증권신고(유동화증권등)',
                    '채권유동화계획/양도등록', '자산유동화관련중요사항발생등신고', '주요사항보고서'
                ])
            elif index == 9:  # I: 거래소공시
                self._cmbPublishDetail.addItems([
                    '전체', '수시공시', '공정공시', '시장조치/안내', '지분공시', '증권투자회사', '채권공시'
                ])
            elif index == 10:  # J: 공정위공시
                self._cmbPublishDetail.addItems([
                    '전체', '대규모내부거래관련', '대규모내부거래관련(구)', '기업집단현황공시',
                    '비상장회사중요사항공시', '기타공정위공시'
                ])


class SearchDocumentSubWindow(CommonReportSubWindow):
    _widget: SearchDocumentWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(dart_obj=dart_obj, parent=parent)
        self.setWindowTitle('공시 검색')

    def initWidget(self, dart_obj: OpenDart = None):
        self._widget = SearchDocumentWidget(dart_obj, self)


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
