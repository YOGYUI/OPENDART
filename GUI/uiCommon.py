from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem


class ReadOnlyTableItem(QTableWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(Qt.ItemFlags(int(self.flags()) ^ Qt.ItemIsEditable))
