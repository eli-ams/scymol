from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from logging_functions import print_to_log, log_function_call

# Load the UI file
Ui_NvtWindow, _ = uic.loadUiType("frontend/uis/lmpstage_nvt.ui")


class LammpsNvtSubstage(QMainWindow):
    """
    Substage window for setting NVT (Canonical Ensemble) properties in a LAMMPS simulation.

    This class provides a GUI window for users to configure the NVT ensemble settings,
    which is crucial for simulations maintaining constant temperature, volume, and particle number.

    Attributes:
        ui (Ui_NvtWindow): The user interface for the NVT substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsNvtSubstage.

        This method sets up the user interface components for the NVT substage,
        including the window title and the UI layout.

        :return: None
        :rtype: None
        """
        super(LammpsNvtSubstage, self).__init__()
        self.ui = Ui_NvtWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("NVT Properties")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method is used to hide the window from view, keeping it inactive
        in the background. It can be shown again when necessary.

        :return: None
        :rtype: None
        """
        self.hide()
