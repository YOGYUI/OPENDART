import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication


if __name__ == '__main__':
    try:
        from opendart import OpenDart
        from GUI import MainWindow

        app = QCoreApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        app.setAttribute(Qt.AA_DontUseNativeMenuBar)
        app.setAttribute(Qt.AA_Use96Dpi)
        app.setStyle('fusion')

        dart = OpenDart()
        wnd = MainWindow(dart)
        wnd.show()
        wnd.raise_()

        app.exec_()
    except Exception as e:
        print(e)

    sys.exit(0)
