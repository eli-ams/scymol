import importlib
import os
import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QMessageBox

from scymol.front2back import validate_inputs as validate_inputs
from scymol.front2back.backend_thread import BackendThread
from scymol.front2back.running_process_dialog import RunningProcessDialog
import scymol.static_functions as static_functions
from typing import Callable
from scymol.logging_functions import print_to_log, log_function_call


class BackendConnector:
    @log_function_call
    def __init__(self, main_window: QWidget) -> None:
        """
        Initialize an instance of YourClassName.

        Args:
            main_window (QWidget): The main window widget.

        Returns:
            None
        """
        self.submit_job = None
        self.job_id = None
        self.backend_thread = None
        self.process_dialog = None
        self.job_submission_error_message = ""
        self.main_window = main_window

        self.qt_substage_inputs = (
            self.main_window.tab3.data_extractor.get_simulation_inputs()
        )
        self.mixture_data = static_functions.generate_mixture_with_smiles(
            mixture_table=self.main_window.mixture_table,
            molecules_objects=self.main_window.molecules_objects,
        )
        self.lammps_stages_and_methods = (
            static_functions.translate_simulation_inputs_to_lammps_stages(
                run_mode=self.main_window.run_mode,
                simulation_inputs=self.qt_substage_inputs,
            )
        )

        self.total_number_of_stages = (
            self.main_window.tab3.selected_stages_widget.count_lammps_substages()
        )

        self.progress_list = [
            [substage + 1 for substage in range(stage)]
            for stage in self.total_number_of_stages
        ]

    @log_function_call
    def validate_inputs(self):
        pass

    @log_function_call
    def write_inputs_to_file(self) -> None:
        """
        Write input parameters to a file  based on the current simulation configuration.

        Returns:
            None
        """
        # validate_inputs.validate_lammps_mpi_environment(
        #     lammps_path=self.main_window.lineedit_mpiexec_path.text(),
        #     mpi_path=self.main_window.lineedit_mpiexec_path.text(),
        #     dir_to_dummy_lammps_sim="front2back/temp_files/dummy_lammps_simulation",
        # )

        if self.main_window.run_mode == "mixture+pysimm+lammps":
            static_functions.write_inputs_to_file(
                file_path=importlib.resources.files("scymol.backend").joinpath(
                    "inputs.py"
                ),
                run_mode=self.main_window.run_mode,
                constants={"avogadro_number": 6.022e23},
                number_of_mixtures_needed=self.main_window.spinbox_nbr_of_mixtures_needed.value(),
                initial_low_density_factor=self.main_window.doublespinbox_initial_density_factor.value(),
                flt_final_density_in_kgm3=self.main_window.doublespinbox_final_density.value(),
                molecules_dictionary=static_functions.convert_molecule_dict(
                    original_dict=self.mixture_data
                ),
                int_multiply_nbr_of_mols_by_factor=1,
                distribution_method=self.main_window.combobox_distribution_method.currentText(),
                molecules_flag="cco",
                layer_offset=self.main_window.doublespinbox_layer_offset.value(),
                file_output_name="cco",
                number_of_trials=500,
                potential_energy_limit=self.main_window.doublespinbox_potential_energy_threshold.value(),
                run_command=self.main_window.lineedit_run_command.text(),
                use_forcefield=self.main_window.combobox_force_field.currentText(),
                charges=self.main_window.combobox_charges.currentText(),
                lammps_stages_and_methods=self.lammps_stages_and_methods,
            )
        elif self.main_window.run_mode == "from_previous_lammps":
            static_functions.write_inputs_to_file(
                file_path=importlib.resources.files("scymol.backend").joinpath(
                    "inputs.py"
                ),
                run_mode=self.main_window.run_mode,
                constants={"avogadro_number": 6.022e23},
                number_of_mixtures_needed=1,
                file_output_name="cco",
                number_of_trials=1,
                run_command=self.main_window.lineedit_run_command.text(),
                lammps_stages_and_methods=self.lammps_stages_and_methods,
            )

    @log_function_call
    def run_backend_thread(self, callback: Callable) -> None:
        """
        Run a backend process in a separate thread and connect a callback function to its completion signal.

        Args:
            callback: The callback function to be executed upon completion of the backend process.

        Returns:
            None
        """
        command = [
            sys.executable,
            str(importlib.resources.files("scymol.backend").joinpath("main.py")),
            "--id",
            f"{self.job_id}",
        ]
        self.backend_thread = BackendThread(command)
        self.backend_thread.finished_signal.connect(callback)
        self.backend_thread.start()

    @log_function_call
    def show_process_dialog(self, parent: QWidget) -> None:
        """
        Show a dialog to display the progress of a running backend process.

        Args:
            parent: The parent window or widget to which the dialog is attached.

        Returns:
            None
        """
        self.process_dialog = RunningProcessDialog(
            parent,
            self.backend_thread,
            self.job_id,
            self.progress_list,
        )
        self.process_dialog.setWindowModality(Qt.NonModal)
        self.process_dialog.show()

    @log_function_call
    def run(self, callback: Callable) -> None:
        """
        Execute a series of steps to initiate and run a backend process.

        Args:
            callback: The callback function to be executed upon completion of the backend process.

        Returns:
            None
        """
        self.get_next_job_id(importlib.resources.files("scymol").joinpath("output"))
        try:
            self.write_inputs_to_file()
        except Exception as e:
            static_functions.display_message(
                message=str(e),
                title="Error initializing simulation.",
                dialog_type="error",
            )
            return
        self.run_backend_thread(callback)
        self.show_process_dialog(self.main_window)

    @log_function_call
    def on_backend_thread_finished(self, return_code: int) -> None:
        """
        Handle the completion of the backend process.

        Args:
            return_code (int): The return code of the subprocess.

        Returns:
            None
        """
        self.process_dialog.accept()
        del self.process_dialog
        del self.backend_thread

    @log_function_call
    def get_next_job_id(self, output_dir: str) -> None:
        """
        Get the next available job ID for the specified output directory.

        Args:
            output_dir (str): The directory where job folders are stored.

        Returns:
            None
        """
        # Initialize the largest ID to 0
        largest_id = 0

        # List the contents of the output directory
        dir_list = os.listdir(output_dir)

        for folder in dir_list:
            try:
                folder_id = int(folder)  # Convert folder name to integer
                largest_id = max(
                    largest_id, folder_id
                )  # Update largest_id if a larger integer is found
            except ValueError:
                # If folder name can't be converted to an integer, ignore it
                continue

        self.job_id = largest_id + 1  # Return the next job ID

    @log_function_call
    def checking_ui_inputs_before_submitting_job(self) -> None:
        """
        Checks UI inputs before submitting a job and displays an error dialog if validation fails.
        """
        self.submit_job = True
        if self.main_window.run_mode == "mixture+pysimm+lammps":
            if not self.validate_molecules():
                self.submit_job = False

        if not self.submit_job:
            static_functions.display_message(
                message=self.job_submission_error_message,
                title="Simulation validation error.",
                dialog_type="error",
            )

    @log_function_call
    def validate_molecules(self) -> bool:
        """
        Validates properties of molecules in a mixture and returns True if all checks pass, False otherwise.
        """
        total_molecules = 0
        for compound, properties in self.mixture_data.items():
            if not isinstance(properties["number"], int) or properties["number"] < 0:
                self.job_submission_error_message = (
                    f"Number of molecules in molecule [{compound}] cannot be negative."
                )
                return False

            if not isinstance(properties["rotate"], bool):
                self.job_submission_error_message = (
                    f"Rotate property in molecule [{compound}] "
                    f"must return a True or False (bool)."
                )
                return False

            if not isinstance(properties["smiles"], str) or not properties["smiles"]:
                self.job_submission_error_message = (
                    f"Smiles string in molecule [{compound}] cannot be empty."
                )
                return False

            total_molecules += properties["number"]

        if total_molecules < 1:
            self.job_submission_error_message = (
                f"Total number of molecules in the system should be at least 1."
            )
            return False

        return True
