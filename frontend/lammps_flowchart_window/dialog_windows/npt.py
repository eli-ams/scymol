from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from logging_functions import print_to_log, log_function_call

# Load the UI file
Ui_NptWindow, _ = uic.loadUiType("frontend/uis/lmpstage_npt.ui")


class LammpsNptSubstage(QMainWindow):
    """
    Substage window for setting NPT (Isothermal-Isobaric Ensemble) properties in a LAMMPS simulation.

    This class represents a GUI window allowing users to configure NPT settings
    as part of a LAMMPS simulation setup process.

    Attributes:
        ui (Ui_NptWindow): The user interface for the NPT substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsNptSubstage.

        This method sets up the user interface components for the NPT substage,
        including window titles and UI elements.

        :return: None
        :rtype: None
        """
        super(LammpsNptSubstage, self).__init__()
        self.ui = Ui_NptWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("NPT Properties")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method is used to hide the window from view, while keeping it active
        in the background. It can be shown again when necessary.

        :return: None
        :rtype: None
        """
        self.hide()
