import importlib

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QWidget
from typing import Optional
from scymol.logging_functions import print_to_log, log_function_call

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath("smiles_window.ui")

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r", encoding="utf8") as f:
    Ui_SmilesWindow, _ = uic.loadUiType(f)


class SmilesWindow(QDialog, Ui_SmilesWindow):
    """
    A dialog window for entering SMILES string and name of a molecule.

    Inherits from QDialog and the generated Ui_SmilesWindow.

    :param parent: The parent widget, defaults to None.
    :type parent: QWidget, optional
    """

    @log_function_call
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the SmilesWindow instance.

        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(SmilesWindow, self).__init__(parent)
        self.input_name: Optional[str] = None
        self.input_smiles: Optional[str] = None
        self.setupUi(self)  # Sets up the UI elements on the QDialog

        self.pushButton.clicked.connect(self.close_window)
        self.lineedit_name.textChanged.connect(self.validate_inputs)
        self.lineedit_smiles.textChanged.connect(self.validate_inputs)
        self.pushButton.setEnabled(False)

    @log_function_call
    def validate_inputs(self) -> None:
        """
        Validate the inputs in the line edits and enable/disable the OK button accordingly.

        :return: None
        :rtype: None
        """
        name_text = self.lineedit_name.text()
        smiles_text = self.lineedit_smiles.text()
        self.pushButton.setEnabled(bool(name_text and smiles_text))

    @log_function_call
    def close_window(self) -> None:
        """
        Close the window, storing the entered SMILES and name.

        :return: None
        :rtype: None
        """
        self.input_smiles = self.lineedit_smiles.text()
        self.input_name = self.lineedit_name.text()
        self.accept()  # Sets the dialog result to Accepted
