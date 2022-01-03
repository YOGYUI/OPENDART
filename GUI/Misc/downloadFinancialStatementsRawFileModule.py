# 재무제표 원본파일(XBRL) 다운로드 UI
import os
import sys
from typing import Union
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QWidget, QLineEdit, QRadioButton, QPushButton, QLabel, QCheckBox, QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QSizePolicy
CURPATH = os.path.dirname(os.path.abspath(__file__))
GUIPATH = os.path.dirname(CURPATH)
PROJPATH = os.path.dirname(GUIPATH)
sys.path.extend([CURPATH, GUIPATH, PROJPATH])
sys.path = list(set(sys.path))
del CURPATH, GUIPATH, PROJPATH
from opendart import OpenDart, ReportCode


class DownloadFinancialStatementsRawFileWindow(QMainWindow):
    _opendart: Union[OpenDart, None] = None

    def __init__(self, dart_obj: OpenDart = None, parent=None):
        super().__init__(parent=parent)
        self._editDocumentNumber = QLineEdit()
        self._radioRptCode1 = QRadioButton('1분기보고서')
        self._radioRptCode2 = QRadioButton('반기보고서')
        self._radioRptCode3 = QRadioButton('3분기보고서')
        self._radioRptCode4 = QRadioButton('사업보고서')
        self._checkOpenFolder = QCheckBox('완료 후 폴더 열기')
        self._btnDownload = QPushButton('다운로드')
        self.initControl()
        self.initLayout()
        self.setOpenDartObject(dart_obj)
        self.setWindowTitle('재무제표 원본파일 다운로드')

    def initLayout(self):
        central = QWidget()
        self.setCentralWidget(central)
        vbox = QVBoxLayout(central)
        vbox.setContentsMargins(4, 4, 4, 4)
        vbox.setSpacing(4)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('접수 번호')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(lbl)
        hbox.addWidget(self._editDocumentNumber)
        vbox.addWidget(subwgt)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        lbl = QLabel('보고서 종류')
        lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
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
        vbox.addWidget(subwgt)

        vbox.addWidget(self._checkOpenFolder)

        subwgt = QWidget()
        subwgt.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        hbox = QHBoxLayout(subwgt)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(4)
        self._btnDownload.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding)
        hbox.addWidget(self._btnDownload)
        vbox.addWidget(subwgt)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

    def initControl(self):
        self._radioRptCode1.setToolTip('11013')
        self._radioRptCode2.setToolTip('11012')
        self._radioRptCode3.setToolTip('11014')
        self._radioRptCode4.setToolTip('11011')
        self._radioRptCode4.setChecked(True)
        self._btnDownload.clicked.connect(self.download)
        self._btnDownload.setIcon(QIcon('./Resource/download.png'))
        self._checkOpenFolder.setChecked(True)

    def release(self):
        pass

    def setOpenDartObject(self, obj: OpenDart):
        self._opendart = obj

    def download(self):
        if self._opendart is None:
            return
        target_dir = QFileDialog.getExistingDirectory(self, '저장할 폴더 선택')
        if len(target_dir) > 0:
            doc_no = self._editDocumentNumber.text()
            if self._radioRptCode1.isChecked():
                rptcode = ReportCode.FirstQuater
            elif self._radioRptCode2.isChecked():
                rptcode = ReportCode.HalfYear
            elif self._radioRptCode3.isChecked():
                rptcode = ReportCode.ThirdQuarter
            else:
                rptcode = ReportCode.Business
            self._opendart.changeDataStoragePath(target_dir)
            openFolder = self._checkOpenFolder.isChecked()
            self._opendart.downloadFinancialStatementsRawFile(doc_no, rptcode, openFolder=openFolder)
            self._opendart.recoverDataStoragePath()


if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QCoreApplication

    dart = OpenDart()

    QApplication.setStyle('fusion')
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    wnd_ = DownloadFinancialStatementsRawFileWindow(dart)
    wnd_.show()
    app.exec_()
