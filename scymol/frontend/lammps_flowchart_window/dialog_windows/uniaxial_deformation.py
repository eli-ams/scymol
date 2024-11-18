import importlib

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow
from scymol.logging_functions import print_to_log, log_function_call

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath(
    "lmpstage_uniaxialdeformation.ui"
)

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r") as f:
    Ui_UniaxialDeformationWindow, _ = uic.loadUiType(f)


class LammpsUniaxialDeformation(QMainWindow):
    """
    Substage window for setting Uniaxial Deformation properties in a LAMMPS simulation.

    This class provides a graphical user interface for configuring the uniaxial deformation
    parameters in a LAMMPS simulation, which is useful for simulations involving strain
    and stress analysis under uniaxial deformation.

    Attributes:
        ui (Ui_UniaxialDeformationWindow): The user interface for the Uniaxial Deformation substage.
    """

    @log_function_call
    def __init__(self) -> None:
        """
        Construct and initialize the LammpsUniaxialDeformation.

        This method sets up the user interface components for the Uniaxial Deformation substage,
        including initializing the window and setting up the UI layout.

        :return: None
        :rtype: None
        """
        super(LammpsUniaxialDeformation, self).__init__()
        self.ui = Ui_UniaxialDeformationWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Uniaxial Deformation")

    @log_function_call
    def hide_window(self) -> None:
        """
        Hide the substage window.

        This method allows for the temporary hiding of the Uniaxial Deformation substage window,
        making it invisible while keeping it active in the background for future use.

        :return: None
        :rtype: None
        """
        self.hide()
