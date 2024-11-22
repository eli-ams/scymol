import importlib

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath("setcell_window.ui")

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r", encoding="utf8") as f:
    Ui_SetCellWindow, _ = uic.loadUiType(f)


class SetCellWindow(QMainWindow):
    def __init__(self, parent=None):
        super(SetCellWindow, self).__init__(parent)
        self.ui = Ui_SetCellWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Set Cell")

    def hide_window(self):
        self.hide()
