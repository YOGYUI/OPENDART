# 지분공시 종합정보 API 관련 UI
import os
import sys
import pandas as pd
from PyQt5.QtWidgets import QVBoxLayout
CURPATH = os.path.dirname(os.path.abspath(__file__))
GUIPATH = os.path.dirname(CURPATH)
PROJPATH = os.path.dirname(GUIPATH)
sys.path.extend([CURPATH, GUIPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, GUIPATH, PROJPATH
from opendart import OpenDart
from uiCommon import CommonReportWidget, CommonReportSubWindow


class ShareDisclosureWidget(CommonReportWidget):
    def __init__(self, dart_obj: OpenDart = None, parent=None):
        self._type_func_list = [
            ('대량보유 상황보고', 'getMajorStockInformation'),
            ('임원ㆍ주요주주 소유보고', 'getExecutiveStockInformation'),
        ]
        super().__init__(dart_obj=dart_obj, parent=parent)

    def initParameterLayout(self, vbox_gr: QVBoxLayout):
        pass

    def initControl(self):
        super().initControl()

    def search(self):
        if not self.checkValidity():
            return

        corp_code_list = self.getCorpCodeListFromEdit()
        index = self._cmbInfoType.currentIndex()
        func_name = self._type_func_list[index][1]
        method_to_call = getattr(self._opendart, func_name)
        df_result = pd.DataFrame()
        for code in corp_code_list:
            df_search = method_to_call(code)
            if df_result.empty:
                for col in df_search.columns:
                    df_result[col] = None
            df_result = df_result.append(df_search, ignore_index=True)

        self.drawTable(df_result)


class ShareDisclosureSubWindow(CommonReportSubWindow):
    _widget: ShareDisclosureWidget

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(dart_obj=dart_obj, parent=parent)
        self.setWindowTitle('지분공시 종합정보')

    def initWidget(self, dart_obj: OpenDart = None):
        self._widget = ShareDisclosureWidget(dart_obj, self)


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
