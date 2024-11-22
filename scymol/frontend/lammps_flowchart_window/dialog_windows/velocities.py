import importlib

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from scymol.logging_functions import print_to_log, log_function_call

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath(
    "lmpstage_velocities.ui"
)

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r", encoding="utf8") as f:
    Ui_VelocitiesWindow, _ = uic.loadUiType(f)


class LammpsVelocitiesSubstage(QMainWindow):
    """
    Substage window for setting Velocity properties in a LAMMPS simulation.

    This class provides a graphical user interface for configuring the initial velocities
    of particles in a LAMMPS simulation.

    Attributes:
        ui (Ui_VelocitiesWindow): The user interface for the Velocities substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsVelocitiesSubstage.

        This method sets up the user interface components for the Velocities substage,
        including initializing the window and setting up the UI layout.

        :return: None
        :rtype: None
        """
        super(LammpsVelocitiesSubstage, self).__init__()
        self.ui = Ui_VelocitiesWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Initialize Velocities")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method is responsible for hiding the Velocities substage window, making it
        invisible to the user while still keeping it active in the background for future use.

        :return: None
        :rtype: None
        """
        self.hide()
