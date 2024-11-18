import importlib
import os
import platform
import shutil
import subprocess
import webbrowser

from PyQt5.QtWidgets import (
    QMenuBar,
    QApplication,
    QFileDialog,
    QDialog,
    QMainWindow,
    QWidget,
    QMessageBox,
)

import scymol
from scymol.frontend.molecule import Molecule

import scymol.static_functions as static_functions
from scymol.frontend.dialog_windows.load_from_lammps import LoadFromLammpsDialog
from typing import Optional
from scymol.logging_functions import print_to_log, log_function_call


class Menubar(QMenuBar):
    """
    A custom menu bar for the main application window.

    This class defines the menu bar of the application, including various actions like loading data from files, saving data, and closing the application.

    :param main_window: The main window of the application.
    :type main_window: QMainWindow
    :param parent: The parent widget, defaults to None.
    :type parent: QWidget, optional
    """

    @log_function_call
    def __init__(
        self, main_window: QMainWindow, parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the Menubar.

        :param main_window: The main window of the application.
        :type main_window: QMainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(Menubar, self).__init__(parent)
        self.main_window = main_window

        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets within the menubar.

        Sets up the various menu items and their actions for the application's menu bar.

        :return: None
        :rtype: None
        """
        pass

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts within the menubar.

        Configures the layout and arrangement of menu items within the menubar.

        :return: None
        :rtype: None
        """
        pass

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect various signals to their corresponding slots.

        Establishes connections between menu actions and their respective functions or methods to be called.

        :return: None
        :rtype: None
        """
        self.main_window.actionExit.triggered.connect(self.close_application)
        self.main_window.actionSave_mixturedetails.triggered.connect(
            self.save_mixture_data
        )
        self.main_window.actionDocumentation.triggered.connect(self.open_scymol_github)
        self.main_window.actionfrom_pickle.triggered.connect(
            self.load_mixture_from_pickle
        )
        self.main_window.actionfrom_csv.triggered.connect(self.load_mixture_from_csv)
        self.main_window.actionLoad_fromlammps.triggered.connect(self.load_from_lammps)
        self.main_window.actionExplore_root.triggered.connect(self.explore_root_folder)

    @log_function_call
    def open_scymol_github(self) -> None:
        """
        Opens the GitHub repository for the Scymol project.

        Launches the default web browser to the Scymol GitHub page,
        providing access to the repository's contents and codebase.

        :return: None
        :rtype: None
        """
        url = "https://github.com/eli-ams/scymol/tree/master"
        webbrowser.open(url)

    @log_function_call
    def load_from_lammps(self) -> None:
        """
        Load data from a previous Lammps run using a dialog.

        Opens a dialog for the user to select LAMMPS output files to be loaded into the application.

        :return: None
        :rtype: None
        """
        dialog = LoadFromLammpsDialog(self.main_window)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self.main_window.run_mode = "from_previous_lammps"

            # Adjusting elements in the main window to accommodate a 'from_previous_lammps' run mode
            self.main_window.tabWidget.widget(0).setEnabled(False)
            self.main_window.tabWidget.widget(1).setEnabled(False)
            self.main_window.tabWidget.setCurrentIndex(2)
            self.main_window.groupbox_lammpsstages.setChecked(True)

            # Processing dialog's inputs:
            structure_file, trajectories_file = dialog.get_user_input()
            if structure_file:
                destination_file = os.path.join("front2back/temp_files", "temp.lmps")
                shutil.copy(structure_file, destination_file)
            if trajectories_file:
                destination_file = os.path.join(
                    "front2back/temp_files", "last.lammpstrj"
                )
                shutil.copy(trajectories_file, destination_file)

                # Extracting the last trajectory from the trajectories file:
                static_functions.get_last_trajectory(
                    file_name=destination_file, output_file=destination_file
                )

    @log_function_call
    def save_mixture_data(self) -> None:
        """
        Save mixture data to a .pkl file using a "Save As" dialog.

        Invokes a file dialog allowing the user to specify the location and name of the file where the mixture data will be saved.

        :return: None
        :rtype: None
        """
        # Open "Save As" dialog
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save Mixture Data", "", "Pickle Files (*.pkl);;All Files (*)"
        )
        if file_name:
            static_functions.save_pickle_object_as_file(
                file_name,
                self.main_window.molecules_objects,
                self.main_window.mixture_table,
            )

    @log_function_call
    def load_mixture_from_pickle(self) -> None:
        """
        Load mixture data from a .pkl file using a file dialog.

        Opens a file dialog for the user to select a .pkl file containing previously saved mixture data.

        :return: None
        :rtype: None
        """
        # Open a file dialog for selecting a .pkl file (native dialog)
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Load Mixture Data", "", "Pickle Files (*.pkl);;All Files (*)"
        )

        # If the user selected a file
        if file_name:
            loaded_data = static_functions.load_pickle_object_from_file(file_name)
            self.main_window.reset_data()
            self.load_rdkit_mols_from_pickle(loaded_data)
            # self.load_mixture_data_from_pickle(loaded_data["mixture_table"])

    @log_function_call
    def load_mixture_from_csv(self) -> None:
        """
        Load mixture data from a .csv file using a file dialog.

        Opens a file dialog for the user to select a .csv file containing mixture data.

        :return: None
        :rtype: None
        """
        # Open a file dialog for selecting a .pkl file (native dialog)
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Load Mixture Data", "", "CSV Files (*.csv);;All Files (*)"
        )

        # If the user selected a file
        if file_name:
            try:
                loaded_molecules = static_functions.csv_to_dict(file_path=file_name)
            except Exception as e:
                static_functions.display_message(
                    message=f"Error parsing file into molecules [{e}]",
                    title="Parsing error",
                    dialog_type="error",
                )

            for name, properties in loaded_molecules.items():
                if not static_functions.is_valid_smiles(smiles=properties["smiles"]):
                    static_functions.display_message(
                        message=f"Error parsing SMILES string into a molecule in [{name}]",
                        title="Parsing error",
                        dialog_type="error",
                    )
                    return
            self.main_window.tabWidget.setCurrentIndex(0)
            self.main_window.reset_data()
            for name, properties in loaded_molecules.items():
                self.main_window.molecules_objects[name] = Molecule(
                    source_type="smiles",
                    source=properties["smiles"],
                    hydrogenate=True,
                    minimize=False,
                    generate_image=True,
                )
                self.main_window.tab1.add_molecule(
                    name=name, number=properties["number"], rotate=properties["rotate"]
                )

    @log_function_call
    def load_rdkit_mol(self, name: str, molecule) -> None:
        """
        Load an RDKit molecule and add it to the application.

        :param name: The name of the molecule.
        :type name: str
        :param molecule: The RDKit molecule object.
        :type molecule: Molecule
        :return: None
        :rtype: None
        """

    @log_function_call
    def load_rdkit_mols_from_pickle(self, molecule_objects_list: dict) -> None:
        """
        Load RDKit molecules from a pickle file and add them to the application.

        :param molecule_objects_list: A dictionary containing molecule objects.
        :type molecule_objects_list: dict
        :return: None
        :rtype: None
        """
        for name, properties in molecule_objects_list.items():
            self.main_window.molecules_objects[name] = Molecule(
                source_type="rdkit_mol",
                source=properties["object"],
                hydrogenate=False,
                minimize=False,
                generate_image=False,
            )
            self.main_window.tab1.add_molecule(
                name=name, number=properties["number"], rotate=properties["rotate"]
            )

    @log_function_call
    def load_mixture_data_from_pickle(self, mixture_data: dict) -> None:
        """
        Load mixture data from a pickle file and update the mixture table.

        :param mixture_data: A dictionary containing mixture data.
        :type mixture_data: dict
        :return: None
        :rtype: None
        """
        # self.mixture_table = mixture_data
        # self.main_window.tab2.mixture_table.setRowCount(0)
        for name, data in mixture_data.items():
            self.main_window.tab2.mixture_table.update_mixture_table(
                name, data["number"], data["rotate"]
            )

    @staticmethod
    def close_application() -> None:
        """
        Close the application.

        Quits the QApplication and closes the entire application.

        :return: None
        :rtype: None
        """
        QApplication.quit()

    @staticmethod
    def explore_root_folder() -> None:
        """
        Open the root folder of the application in the file explorer.

        Depending on the operating system, opens the current directory of the application in the native file explorer.

        :return: None
        :rtype: None
        """
        # Use importlib.resources to get a path to the package
        with importlib.resources.path("scymol", "__init__.py") as package_root:
            current_directory = package_root.parent

        system_platform = platform.system()

        if system_platform == "Windows":
            subprocess.Popen(["explorer", current_directory])
        elif system_platform == "Linux":
            subprocess.Popen(["xdg-open", current_directory])
        elif system_platform == "Darwin":
            subprocess.Popen(["open", current_directory])
        else:
            error_dialog = QMessageBox()
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setText(f"Cannot open files explorer.")
            error_dialog.setWindowTitle("Platform not supported.")
            error_dialog.exec_()
