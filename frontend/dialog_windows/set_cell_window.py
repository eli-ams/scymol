from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow

Ui_SetCellWindow, _ = uic.loadUiType("frontend/uis/setcell_window.ui")


class SetCellWindow(QMainWindow):
    def __init__(self, parent=None):
        super(SetCellWindow, self).__init__(parent)
        self.ui = Ui_SetCellWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Set Cell")

    def hide_window(self):
        self.hide()
