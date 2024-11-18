import importlib

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QFileDialog, QWidget
from typing import Tuple, Optional
from scymol.logging_functions import print_to_log, log_function_call

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath(
    "load_from_lammps_dialog.ui"
)

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r") as f:
    Ui_LoadFromLammpsDialog, _ = uic.loadUiType(f)


class LoadFromLammpsDialog(QDialog):
    """
    A dialog for loading data from LAMMPS input files.

    Inherits from QDialog.
    """

    @log_function_call
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the LoadFromLammpsDialog instance.

        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(LoadFromLammpsDialog, self).__init__(parent)
        self.ui = Ui_LoadFromLammpsDialog()
        self.ui.setupUi(self)
        self.connect_signals()

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals from UI elements to their respective slots.

        :return: None
        :rtype: None
        """
        self.ui.pushButton.clicked.connect(self.load_file_line_edit)
        self.ui.pushButton_2.clicked.connect(self.load_file_line_edit_2)

    @log_function_call
    def load_file_line_edit(self) -> None:
        """
        Open a file dialog and update the first line edit with the selected file path.

        :return: None
        :rtype: None
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if file_path:
            self.ui.lineEdit.setText(file_path)

    @log_function_call
    def load_file_line_edit_2(self) -> None:
        """
        Open a file dialog and update the second line edit with the selected file path.

        :return: None
        :rtype: None
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File")
        if file_path:
            self.ui.lineEdit_2.setText(file_path)

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the dialog window.

        :return: None
        :rtype: None
        """
        self.hide()

    @log_function_call
    def get_user_input(self) -> Tuple[str, Optional[str]]:
        """
        Retrieve user input from the dialog's line edits.

        :return: A tuple containing the text from the first line edit and optionally the second line edit (if the associated group box is checked).
        :rtype: Tuple[str, Optional[str]]
        """
        text1 = self.ui.lineEdit.text()
        group_checked = self.ui.groupBox_2.isChecked()
        text2 = self.ui.lineEdit_2.text() if group_checked else None

        return text1, text2
