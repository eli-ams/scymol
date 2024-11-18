import psutil
from PyQt5.QtWidgets import QWidget
from typing import Optional

import scymol.static_functions as static_functions
from scymol.logging_functions import print_to_log, log_function_call


class Tab4(QWidget):
    """
    A widget representing the fourth tab in the main application window.

    This tab manages settings and controls related to backend processes.

    :param main_window: The main window of the application.
    :type main_window: QMainWindow
    :param parent: The parent widget, defaults to None.
    :type parent: QWidget, optional
    """

    @log_function_call
    def __init__(
        self, main_window: "MainWindow", parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize Tab4.

        :param main_window: The main window of the application.
        :type main_window: QMainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(Tab4, self).__init__(parent)
        self.default_command = None
        self.main_window = main_window
        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()
        self.update_run_command()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets within Tab4.

        :return: None
        :rtype: None
        """
        cpu_count = psutil.cpu_count(logical=False)
        self.main_window.spinbox_number_of_processes.setValue(cpu_count)
        self.main_window.spinbox_number_of_processes.setMaximum(cpu_count)

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts within Tab4.

        :return: None
        :rtype: None
        """
        pass

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals within Tab4.

        :return: None
        :rtype: None
        """
        self.main_window.lineedit_lammps_path.textChanged.connect(
            self.update_run_command
        )
        self.main_window.lineedit_mpiexec_path.textChanged.connect(
            self.update_run_command
        )
        self.main_window.spinbox_number_of_processes.valueChanged.connect(
            self.update_run_command
        )
        self.main_window.groupBox_6.toggled.connect(self.toggle_run_command_editability)

        # Existing connection
        self.main_window.tab4_pushbutton_run.clicked.connect(
            self.main_window.connect_to_backend
        )

    @log_function_call
    def update_run_command(self) -> None:
        """
        Update the run command based on the current values of the lammps path,
        mpiexec path, and number of processes.

        :return: None
        :rtype: None
        """
        lammps_path = self.main_window.lineedit_lammps_path.text()
        mpiexec_path = self.main_window.lineedit_mpiexec_path.text()
        num_processes = self.main_window.spinbox_number_of_processes.value()

        command = f"{mpiexec_path} -n {num_processes} {lammps_path} -in stage_1.in"
        self.main_window.lineedit_run_command.setText(command)

    @log_function_call
    def toggle_run_command_editability(self, checked: bool) -> None:
        """
        Enable or disable the run command line edit based on the check state
        of groupBox_6.

        :param checked: The check state of groupBox_6.
        :type checked: bool
        :return: None
        :rtype: None
        """
        if checked:
            static_functions.display_message(
                title="Warning: editing command to run",
                message="Exercise caution when manually altering the execution command.\n"
                "Add or remove specific MPI and LAMMPS flags as necessary.",
                dialog_type="warning",
            )
            self.default_command = self.main_window.lineedit_run_command.text()
        self.main_window.lineedit_run_command.setEnabled(checked)
