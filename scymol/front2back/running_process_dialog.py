import importlib
import os
import platform
import subprocess

from PyQt5 import uic
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QDialog, QMessageBox
import scymol.front2back.fron2back_static_functions as fron2back_static_functions
from scymol.logging_functions import print_to_log, log_function_call

# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath("process_dialog.ui")

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r") as f:
    Ui_ProcessDialog, _ = uic.loadUiType(f)


class RunningProcessDialog(QDialog):
    """
    A dialog for displaying the progress of a running backend process.

    This dialog provides a graphical interface to display the output log of a running backend process.
    """

    @log_function_call
    def __init__(
        self, parent: object, backend_thread: object, job_id: int, progress_list: list
    ) -> None:
        """
        Initialize a RunningProcessDialog instance.

        :param parent: The parent window or widget.
        :param backend_thread: The backend thread connected to the dialog.
        :param job_id: The job ID associated with the backend process.
        :param progress_list: List containing progress information for various stages.
        :raises Exception: If no backend thread is provided.
        """

        self.current_mixture = None
        self.files_list = None
        self.user_terminated = False
        self.job_id = job_id
        if not backend_thread:
            raise Exception(
                "No thread connected to window. Please pass backend_thread argument."
            )
        super(RunningProcessDialog, self).__init__(parent)
        self.number_of_mixtures_needed = parent.spinbox_nbr_of_mixtures_needed.value()
        self.progress_list = progress_list
        self.ui = Ui_ProcessDialog()
        self.ui.setupUi(self)
        self.backend_thread = backend_thread  # store a reference to the backend thread

        # Timer to read log file
        self.timer = QTimer()
        self.timer.start(1000)  # Every 1000 milliseconds (1 second)
        self.time_elapsed = 0
        self.ui.progressBar_2.setMaximum(self.number_of_mixtures_needed)

        # Connect signals
        self.connect_signals()

    def update_mixture_progress_bar(self) -> None:
        """
        Update the progress bar based on the mixture processing stage.

        This method updates the progress bar to reflect the current stage of mixture processing.

        :return: None
        :rtype: None
        """

        # Get the latest mixture folder by count.
        self.current_mixture = int(
            (
                fron2back_static_functions.get_latest_mixture_folder_by_count(
                    output_dir=importlib.resources.files("scymol").joinpath(
                        "output", f"{self.job_id}"
                    )
                )
            ).split("_")[-1]
        )

        # Update the progress bar's value.
        self.ui.progressBar_2.setValue(self.current_mixture)
        progress_text = (
            f"Mixture {self.current_mixture} of {self.number_of_mixtures_needed}"
        )
        self.ui.progressBar_2.setFormat(progress_text)

    def update_lammps_stage_progress_bar(self) -> None:
        """
        Update the LAMMPS stage progress bar.

        This method updates the progress bar based on the progress of the LAMMPS simulation stages.

        :return: None
        :rtype: None
        """

        try:
            (
                total_progress,
                total_substages,
            ) = fron2back_static_functions.calculate_progress(
                directory=importlib.resources.files("scymol").joinpath(
                    "output", f"{self.job_id}", f"mixture_{self.current_mixture}"
                ),
                list_of_progress=self.progress_list,
            )
            progress_percentage = (total_progress / total_substages) * 100

            self.ui.progressBar.setMaximum(total_substages)
            self.ui.progressBar.setValue(total_progress)
            self.ui.progressBar.setFormat(
                f"Substage {total_progress} of {total_substages} ({progress_percentage:.2f}%)"
            )
        except Exception as e:
            print(e)

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect any signals and slots for the main window.

        :return: None
        :rtype: None
        """

        self.ui.pushButton.clicked.connect(self.terminate_job)
        self.ui.pushButton_2.clicked.connect(self.explore_output_folder)

        self.backend_thread.finished_signal.connect(self.display_simulation_errors)
        self.timer.timeout.connect(self.read_log_file)
        self.timer.timeout.connect(self.update_time_elapsed)
        self.timer.timeout.connect(self.update_mixture_progress_bar)
        self.timer.timeout.connect(self.update_lammps_stage_progress_bar)

    def display_simulation_errors(self, code: int, message: str) -> None:
        """
        Display any errors that occurred during the simulation.

        :param code: The exit code of the simulation.
        :param message: The error message to be displayed.

        :return: None
        :rtype: None
        """

        self.ui.textedit_strerror.append(message)
        if code != 0:
            if self.user_terminated:
                self.ui.textedit_strerror.append("User terminated the job")
                self.ui.label.setText(f"User terminated the job.")
            else:
                self.ui.label.setText(
                    f"Job terminated due to an error with code {code}."
                )
            self.ui.tabWidget.setCurrentIndex(1)
        else:
            self.ui.label.setText(f"Job terminated successfully.")
        self.ui.pushButton.setEnabled(False)
        self.timer.stop()

    def update_time_elapsed(self) -> None:
        """
        Update the time elapsed since the dialog was opened.

        This method updates the title of the dialog window with the time elapsed.
        :return: None
        :rtype: None
        """

    def read_log_file(self) -> None:
        """
        Read the log file and update the displayed content.
        :return: None
        :rtype: None
        """

        try:
            with open(
                importlib.resources.files("scymol").joinpath(
                    "output", str(self.job_id), "log.txt"
                ),
                "r",
            ) as f:
                content = f.read()
            self.ui.textedit_logout.setPlainText(content)

            text_cursor = self.ui.textedit_logout.textCursor()
            text_cursor.movePosition(QTextCursor.End)
            self.ui.textedit_logout.setTextCursor(text_cursor)
        except Exception as e:
            print(f"An error occurred: {e}")

    @log_function_call
    def explore_output_folder(self) -> None:
        """
        Opens the file explorer or file manager for the current working directory.
        :return: None
        :rtype: None
        """

        current_job_directory = importlib.resources.files("scymol").joinpath(
            "output", f"{self.job_id}"
        )
        system_platform = platform.system()

        if system_platform == "Windows":
            subprocess.Popen(["explorer", current_job_directory])
        elif system_platform == "Linux":
            subprocess.Popen(["xdg-open", current_job_directory])
        elif system_platform == "Darwin":
            subprocess.Popen(["open", current_job_directory])
        else:
            error_dialog = QMessageBox()
            error_dialog.setIcon(QMessageBox.Critical)
            error_dialog.setText(f"Cannot open files explorer.")
            error_dialog.setWindowTitle()
            error_dialog.exec_()

    @log_function_call
    def closeEvent(self, event: object) -> None:
        """
        Handle the event when the dialog is closed.

        :param event: The close event.
        :return: None
        :rtype: None
        """

        if self.backend_thread is not None:
            self.backend_thread.terminate_process()  # terminate the process when dialog is closed
        super(RunningProcessDialog, self).closeEvent(
            event
        )  # call the superclass method to actually close the dialog
        self.timer.stop()  # Stop the timer when the dialog is closed

    @log_function_call
    def terminate_job(self) -> None:
        """
        Terminate job without closing the window.
        :return: None
        :rtype: None
        """

        if self.backend_thread is not None:
            self.backend_thread.terminate_process()  # terminate the process when dialog is closed

        self.timer.stop()  # Stop the timer when the job is terminated
        self.ui.pushButton.setEnabled(False)
        self.user_terminated = True
