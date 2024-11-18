import importlib.resources as importlib_resources
import sys
import scymol.static_functions as static_functions
from scymol.logging_functions import print_to_log, log_function_call
import scymol.prechecks
import psutil
from typing import Optional, Dict, Any
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QTimer
from scymol.front2back.backend_connector import BackendConnector
from scymol.frontend.context_menus.load_molecules import LoadMoleculesContextMenu
from scymol.frontend.main_window.menubar import Menubar
from scymol.frontend.main_window.tab1 import Tab1
from scymol.frontend.main_window.tab2 import Tab2
from scymol.frontend.main_window.tab3 import Tab3
from scymol.frontend.main_window.tab4 import Tab4
from scymol.frontend.main_window.tab5 import Tab5
from scymol.frontend.settingsfile import SettingsFile

# Resolve the full path to the .ui file
ui_path = importlib_resources.files("scymol.frontend.uis").joinpath("main_window.ui")

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r") as f:
    Ui_MainWindow, BaseMainWindow = uic.loadUiType(f)


class MainWindow(BaseMainWindow):
    """
    MainWindow class extends QMainWindow and serves as the central
    user interface window for the application.
    """

    @log_function_call
    def __init__(self, parent: Optional[QMainWindow] = None) -> None:
        """
        Initialize the MainWindow instance.

        This method sets up the main window of the application. It initializes various attributes,
        settings, UI components, layouts, tabs, menus, and connections for signals. Additionally,
        it configures a system usage timer to periodically update system usage information.

        :param parent: An optional parent window (instance of QMainWindow) for the main window.
                       If provided, the main window will be set as a child of the parent window.
                       Defaults to None, indicating no parent.
        :type parent: Optional[QMainWindow]

        The initialization process includes:
        - Initializing attributes and settings.
        - Loading the user interface.
        - Setting initial configurations based on startup settings.
        - Setting the window title.
        - Initializing widgets and layouts.
        - Creating tabs and menus.
        - Connecting signals for event handling.
        - Setting up a timer for system usage updates.

        The method sets up `system_usage_timer` to trigger every second (1000 milliseconds),
        invoking the `get_system_usage` method.

        Attributes initialized:
        - settings_file: An instance of SettingsFile to manage application settings.
        - run_mode: A string indicating the run mode of the application.
        - system_usage_timer: A QTimer instance for updating system usage information.

        """
        super(MainWindow, self).__init__(parent)
        self.initialize_attributes()
        self.settings_file = SettingsFile(
            filename=importlib_resources.files("scymol").joinpath("config.json")
        )
        self.settings_file.load_or_create_settings()
        self.load_ui()
        self.initialize_startup_settings()
        self.set_window_title()
        self.initialize_widgets()
        self.initialize_layouts()
        self.initialize_tabs_and_menu()
        self.connect_signals()
        self.run_mode = "mixture+pysimm+lammps"

        self.system_usage_timer = QTimer(self)
        self.system_usage_timer.timeout.connect(self.get_system_usage)
        self.system_usage_timer.start(1000)  # Timer set to 1 second (1000 milliseconds)

        print_to_log(message="Initialized MainWindow instance.")

    @log_function_call
    def initialize_attributes(self) -> None:
        """
        Initialize data attributes for the main window.

        This function initializes data attributes used in the main window of the program.

        :return: None
        :rtype: None
        """
        self.qt_substage_inputs: Optional[Any] = None
        self.mixture_table: Dict = {}
        self.mixture_data: Dict = {}
        self.molecules_objects: Dict = {}

    @log_function_call
    def initialize_startup_settings(self):
        """
        Initialize startup settings.

        This function initializes startup settings for the PyQt5 program. It sets the window
        resolution based on saved settings and updates the LAMMPS and MPI paths.

        :return: None
        :rtype: None
        """
        self.resize(
            self.settings_file.settings["resolution_width"],
            self.settings_file.settings["resolution_height"],
        )
        self.lineedit_lammps_path.setText(
            self.settings_file.settings["lammps_location"]
        )
        self.lineedit_mpiexec_path.setText(self.settings_file.settings["mpi_location"])

    @log_function_call
    def load_ui(self) -> None:
        """
        Load the user interface (UI) layout from the specified file.

        This function loads the UI layout from the specified file "frontend/uis/main_window.ui"
        into the current PyQt5 main window instance.

        :return: None
        :rtype: None
        """
        # Resolve the full path to the .ui file
        ui_path = importlib_resources.files("scymol.frontend.uis").joinpath(
            "main_window.ui"
        )

        # Load the UI file with the resolved path
        uic.loadUi(ui_path, self)

    @log_function_call
    def set_window_title(self) -> None:
        """
        Set the window title for the main window.

        This function sets the window title of the main window to "Create an MD Mixture".

        :return: None
        :rtype: None
        """
        self.setWindowTitle("Scymol 2024")

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets with specific settings.

        This function is intended to initialize any widgets that require specific settings,
        although it currently does not contain any specific implementation.

        :return: None
        :rtype: None
        """
        pass

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts with specific settings.

        This function is intended to initialize any layouts that require specific settings,
        although it currently does not contain any specific implementation.

        :return: None
        :rtype: None
        """
        pass

    @log_function_call
    def initialize_tabs_and_menu(self) -> None:
        """
        Initialize tabs and menu bar for the main window.

        This function initializes tabs and a menu bar for the main window of the PyQt5 program.
        It creates instances of Tab1, Tab2, Tab3, Tab4, Tab5, Menubar, and LoadMoleculesContextMenu.

        :return: None
        :rtype: None
        """
        self.tab1 = Tab1(self)
        self.tab2 = Tab2(self)
        self.tab3 = Tab3(self)
        self.tab4 = Tab4(self)
        self.tab5 = Tab5(self)
        self.menubar = Menubar(self)
        self.load_molecule_context_menu = LoadMoleculesContextMenu(self)

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals and slots for the main window.

        This function establishes signal-slot connections for the main window of the PyQt5 program.
        It connects the clicked signal of the 'addMoleculeButton' widget to the
        'create_loadmolecules_menu' slot of the 'load_molecule_context_menu'.

        :return: None
        :rtype: None
        """
        self.addMoleculeButton.clicked.connect(
            self.load_molecule_context_menu.create_loadmolecules_menu
        )

    @log_function_call
    def connect_to_backend(self) -> None:
        """
        Establish a connection to the backend and execute computations.

        This function is responsible for establishing a connection to the backend for executing computations.
        It utilizes the 'BackendConnector' class to perform this task, checking UI inputs before
        submitting the job and running the computation when necessary.

        :return: None
        :rtype: None
        """
        backend_connector = BackendConnector(self)
        backend_connector.checking_ui_inputs_before_submitting_job()
        if backend_connector.submit_job:
            backend_connector.run(backend_connector.on_backend_thread_finished)
        else:
            del backend_connector

    @log_function_call
    def reset_data(self) -> None:
        """
        Reset data tables and lists, effectively clearing the UI's dataframes.

        This function clears the data stored in various tables and lists within the user interface,
        effectively resetting the UI's dataframes. It clears the 'mixture_table', 'moleculeList',
        'molecules_objects', and the 'mixture_table' within 'tab2'.

        :return: None
        :rtype: None
        """
        self.mixture_table.clear()
        self.tab1.moleculeList.clear()
        self.molecules_objects.clear()
        self.tab2.mixture_table.setRowCount(0)

    def get_system_usage(self) -> None:
        """
        Retrieve and display system usage information.

        This function retrieves and displays system usage information, including CPU and RAM usage,
        and updates the status bar of the main window with this information.

        :return: None
        :rtype: None
        """
        cpu_percent = psutil.cpu_percent()
        ram_percent = psutil.virtual_memory().percent
        self.statusBar().showMessage(
            f"CPU Usage: {cpu_percent}%, RAM Usage: {ram_percent}%"
        )


@log_function_call
def main() -> None:
    """
    Entry point for the application.

    This function serves as the entry point for the application. It initializes QApplication,
    sets the application style to "Fusion," creates the MainWindow, displays it, and enters
    the main event loop.

    :return: None
    :rtype: None
    """
    app = QApplication([])
    # app.setStyle(QStyleFactory.create("Fusion"))
    window = MainWindow()
    window.show()
    app.exec_()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        static_functions.display_message(
            message=f"The frontend of Scymol has found an error:\n" f"{e}",
            title="UI must close.",
            dialog_type="error",
        )
        print_to_log(
            message=f"The frontend of Scymol has found an error:\n" f"{e}",
            level="critical",
        )
        sys.exit(1)
