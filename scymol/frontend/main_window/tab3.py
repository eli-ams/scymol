import importlib
import os
import platform
import subprocess
from pathlib import Path

import pysimm.system as pysimm_system
from pysimm import forcefield as pysimm_forcefield
from PyQt5.QtWidgets import QWidget, QListWidget
from scymol.front2back.data_extractor import DataExtractor
from scymol.frontend.custom_qtwidgets.list_of_stages_widget import ListOfStagesWidget
from typing import Optional
from scymol.logging_functions import print_to_log, log_function_call
from scymol.static_functions import write_temp_mol_file, display_message


class Tab3(QWidget):
    """
    A widget representing the third tab in the main application window.

    This tab manages the workflow stages for the application, allowing users to select and arrange stages.

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
        Initialize Tab3.

        :param main_window: The main window of the application.
        :type main_window: QMainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(Tab3, self).__init__(parent)
        self.data_extractor: Optional[DataExtractor] = None
        self.stages_counter: Optional[dict] = None
        self.selected_stages_widget: Optional[ListOfStagesWidget] = None
        self.available_stages_widget: Optional[QListWidget] = None
        self.main_window = main_window
        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets within Tab3.

        :return: None
        :rtype: None
        """
        self.available_stages_widget = QListWidget()
        self.available_stages_widget.setObjectName("available_stages_widget")
        self.available_stages_widget.setDragEnabled(True)
        self.available_stages_widget.addItems(["LAMMPS Stage"])

        self.selected_stages_widget = ListOfStagesWidget(self)
        self.stages_counter = self.selected_stages_widget.stages_counter

        self.data_extractor = DataExtractor(self.selected_stages_widget)

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts within Tab3.

        :return: None
        :rtype: None
        """
        self.main_window.horizontalLayout_3.addWidget(self.available_stages_widget)
        self.main_window.horizontalLayout_3.addWidget(self.selected_stages_widget)

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals within Tab3.

        :return: None
        :rtype: None
        """
        # Existing connection
        self.main_window.pushbutton_test_forcefield_test.clicked.connect(
            lambda: self.test_force_field(True)
        )
        self.main_window.pushbutton_edit_forcefield_test.clicked.connect(
            self.edit_force_field
        )
        pass

    @log_function_call
    def test_force_field(self, verbose):
        """
        Test the application of a force field atomic types and charges to molecular objects.

        :param verbose: If True, display success messages; otherwise, suppress them.
        :type verbose: bool
        :return: True if all operations succeed, False if any error occurs.
        :rtype: bool
        """
        force_field = self.main_window.combobox_force_field.currentText()
        charges = self.main_window.combobox_charges.currentText()
        temp_file = (
            Path(importlib.resources.files("scymol")) / "temp.mol"
        )  # Define the temporary file name once.

        try:
            for key, value in self.main_window.molecules_objects.items():
                write_temp_mol_file(value.mol_obj, temp_file)
                mol_system = pysimm_system.read_mol(temp_file)
                mol_system.apply_forcefield(
                    f=getattr(pysimm_forcefield, force_field)(),
                    charges=charges,
                )
        except Exception as e:
            # Always display error messages regardless of verbose.
            display_message(
                title="Error",
                message=(
                    f"Unable to assign {force_field} types and {charges} charges.\n"
                    f"Try another force field or a different molecular structure."
                ),
                dialog_type="error",
            )
            return False  # Return False if any error occurs.
        else:
            # Display success messages only if verbose is True.
            if verbose:
                display_message(
                    title="Information",
                    message=f"Successfully assigned {force_field} types and {charges} charges.\n",
                    dialog_type="information",
                )
            return True  # Return True if all operations succeed.
        finally:
            # Always remove the temporary file, regardless of success or failure.
            if os.path.exists(temp_file):
                os.remove(temp_file)

    @log_function_call
    def edit_force_field(self):
        """
        Open the selected force field file for editing using the default text editor.

        :return: None
        :rtype: None
        """
        force_field = self.main_window.combobox_force_field.currentText()
        # Extract the file to a temporary path
        for extension in ["xml", "json"]:
            try:
                with importlib.resources.path(
                    "pysimm.data.forcefields", f"{force_field}.{extension}".lower()
                ) as file_path:
                    file_path = str(file_path)  # Ensure it's a string path

                    if not os.path.exists(file_path):
                        continue  # Skip if the file doesn't exist

                    # Open with the default text editor
                    if platform.system() == "Windows":
                        os.startfile(file_path)
                    else:  # Linux/Unix
                        subprocess.run(["xdg-open", file_path], check=True)
                    return
            except Exception as e:
                print(e)
                display_message(
                    title="Error",
                    message=f"Unable to open the force field file.\n" f"Error: {e}.",
                    dialog_type="error",
                )
