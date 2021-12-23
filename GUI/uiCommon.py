from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QTableWidgetItem, QAction


class ReadOnlyTableItem(QTableWidgetItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlags(Qt.ItemFlags(int(self.flags()) ^ Qt.ItemIsEditable))


def makeQAction(**kwargs):
    parent = kwargs.get('parent')
    text = kwargs.get('text')
    iconPath = kwargs.get('iconPath')
    triggered = kwargs.get('triggered')
    checkable = kwargs.get('checkable', False)
    checked = kwargs.get('checked', False)

    action = QAction(parent)
    action.setText(text)
    action.setIcon(QIcon(iconPath))
    if triggered is not None:
        action.triggered.connect(triggered)
    action.setCheckable(checkable)
    action.setChecked(checked)

    return action
