import importlib

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from scymol.logging_functions import print_to_log, log_function_call

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath(
    "lmpstage_initialize.ui"
)

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r", encoding="utf8") as f:
    Ui_InitializeWindow, _ = uic.loadUiType(f)


class LammpsInitializeSubstage(QMainWindow):
    """
    Substage window for initializing properties in LAMMPS simulation.

    This class represents a window in the GUI responsible for initializing various
    properties and parameters related to a LAMMPS simulation.

    Attributes:
        ui (Ui_InitializeWindow): The user interface for the initialization substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsInitializeSubstage.

        This constructor sets up the UI components and configurations for the initialization substage.

        :return: None
        :rtype: None
        """
        super(LammpsInitializeSubstage, self).__init__()
        self.ui = Ui_InitializeWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Initialize Properties")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method is used to hide the substage window, effectively making it invisible in the GUI,
        yet still existing in memory and can be shown again when needed.

        :return: None
        :rtype: None
        """
        self.hide()
