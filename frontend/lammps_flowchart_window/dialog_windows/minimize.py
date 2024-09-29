from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from logging_functions import print_to_log, log_function_call

# Load the UI file
Ui_MinimizeWindow, _ = uic.loadUiType("frontend/uis/lmpstage_minimize.ui")


class LammpsMinimizeSubstage(QMainWindow):
    """
    Substage window for minimizing properties in a LAMMPS simulation.

    This class represents a window in the GUI for setting up minimization parameters
    in a LAMMPS simulation.

    Attributes:
        ui (Ui_MinimizeWindow): The user interface for the minimize substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsMinimizeSubstage.

        This constructor initializes the UI components for the minimization substage,
        setting up the necessary widgets and configurations.

        :return: None
        :rtype: None
        """
        super(LammpsMinimizeSubstage, self).__init__()
        self.ui = Ui_MinimizeWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Minimize Properties")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method is used to hide the minimize substage window from view, while keeping it
        active in the background, allowing it to be shown again later if needed.

        :return: None
        :rtype: None
        """
        self.hide()
