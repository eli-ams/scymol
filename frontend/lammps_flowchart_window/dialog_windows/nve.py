from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from logging_functions import print_to_log, log_function_call

# Load the UI file
Ui_NveWindow, _ = uic.loadUiType("frontend/uis/lmpstage_nve.ui")


class LammpsNveSubstage(QMainWindow):
    """
    Substage window for setting NVE (Microcanonical Ensemble) properties in a LAMMPS simulation.

    This class represents a GUI window for configuring the NVE ensemble settings
    in a LAMMPS simulation, which is crucial for simulations maintaining constant
    energy, volume, and particle number.

    Attributes:
        ui (Ui_NveWindow): The user interface for the NVE substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsNveSubstage.

        This method sets up the user interface components for the NVE substage,
        including the window title and the UI layout.

        :return: None
        :rtype: None
        """
        super(LammpsNveSubstage, self).__init__()
        self.ui = Ui_NveWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("NVE Properties Editor")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method is responsible for hiding the window from view, making it
        invisible while still keeping it active in the background. It can be
        shown again as needed.

        :return: None
        :rtype: None
        """
        self.hide()
