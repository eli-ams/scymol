import os

from PyQt5 import QtCore
from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import (
    QWidget,
    QFileSystemModel,
    QTableWidgetItem,
    QMessageBox,
    QMainWindow,
)

from frontend.main_window.lammps_syntax_highlighter import LammpsSyntaxHighlighter
from frontend.main_window.custom_table_widget import CustomTableWidget
from frontend.main_window.instantaneous_properties_file import (
    InstantaneousPropertiesClass,
)
from frontend.main_window.trajectories_file_class import (
    TrajectoriesClass,
)

from typing import Optional, Dict, List
from logging_functions import print_to_log, log_function_call


class Tab5(QWidget):
    @log_function_call
    def __init__(
        self, main_window: QMainWindow, parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the Tab5 widget.

        :param main_window: Reference to the main window of the application.
        :param parent: The parent widget, optional.
        :return: None
        :rtype: None
        """

        super(Tab5, self).__init__(parent)
        self.trajectory_instance = None
        self.lammpstrj_file = None
        self.main_window = main_window
        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize the widgets for Tab5, setting up the file explorer and table widget.

        :return: None
        :rtype: None
        """

        # The directory you want the file explorer to be restricted to
        start_directory = "output/"

        # Set up the file system model
        self.model = QFileSystemModel()
        self.model.setRootPath(start_directory)

        # Set the name filters and apply them to the model
        name_filters = ["*.out", "*.in", "*.txt", "*.log", "*.lammpstrj"]
        self.model.setNameFilters(name_filters)
        self.model.setNameFilterDisables(
            False
        )  # Files not matching the filter are hidden

        # Configure the treeView with the model
        self.main_window.treeView.setModel(self.model)
        self.main_window.treeView.setRootIndex(self.model.index(start_directory))

        # Apply sorting by name, descending
        self.main_window.treeView.sortByColumn(
            0, QtCore.Qt.DescendingOrder
        )  # Column 0 corresponds to the name

        # Optional adjustments
        self.main_window.treeView.setColumnWidth(0, 250)
        self.main_window.treeView.setAlternatingRowColors(True)

        # Hide the parent directory item to prevent navigating up
        self.main_window.treeView.setHeaderHidden(
            True
        )  # Optional: hide the header if desired
        self.main_window.treeView.hideColumn(1)  # Hide size column
        self.main_window.treeView.hideColumn(2)  # Hide type column
        self.main_window.treeView.hideColumn(3)  # Hide date modified column

        self.main_window.tableWidget = CustomTableWidget(
            data={
                "TimeStep": {
                    "Mean": 3000.0,
                    "Standard Deviation": 1581.13,
                    "Standard Error": 707.2,
                    "Confidence Interval Left": 1036.75,
                    "Confidence Interval Right": 4963.24,
                    "Coefficient of Variation": 52.70,
                    "Max": 5000.0,
                    "Min": 1000.0,
                },
            }
        )
        self.main_window.splitter.addWidget(self.main_window.tableWidget)

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize the layouts for Tab5. Currently, this method is a placeholder.

        :return: None
        :rtype: None
        """

        self.main_window.tableWidget.hide()
        pass  # Your layout setup will remain here

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect UI signals to their respective slots for interaction handling.

        :return: None
        :rtype: None
        """

        # Connect the clicked signal of the tree view to the slot
        self.main_window.treeView.clicked.connect(self.on_file_clicked)
        self.main_window.pushButton_trajectory.clicked.connect(
            self.on_pushbutton_trajectory_clicked
        )

    @log_function_call
    def on_file_clicked(self, index: QModelIndex) -> None:
        """
        Handle the event when a file is clicked in the tree view.

        :param index: The model index of the clicked item in the tree view.
        :return: None
        :rtype: None
        """

        file_path = self.model.filePath(index)

        # Check if it's a file and not a directory
        if os.path.isfile(file_path):
            file_size = os.path.getsize(file_path)
            max_size = 5000 * 1024 * 1024  # 50 MB in bytes

            if file_size > max_size:
                # Show warning message
                msgBox = QMessageBox(self)
                msgBox.setIcon(QMessageBox.Warning)
                msgBox.setWindowTitle("File Size Limit Exceeded")
                msgBox.setText(
                    "The size of the file is greater than 50MB - file will not be displayed."
                )
                msgBox.setStandardButtons(QMessageBox.Ok)
                msgBox.exec_()
                return  # Do not proceed with opening the file

            if file_path.endswith(".out"):
                # Clearing previous contents
                self.clear_any_loaded_data()

                # Handle the regular opening of .out file
                self.open_out_file_regular(file_path)
            elif file_path.endswith(".lammpstrj"):
                # Clearing previous contents
                self.clear_any_loaded_data()
                self.open_trajectories_file_regular(file_path)
                self.lammpstrj_file = file_path
            else:
                # For other file types, open them immediately
                self.open_other_file_types(file_path)
        else:
            # Clear the QTextEdit if a directory is clicked
            self.clear_any_loaded_data()

    @log_function_call
    def clear_any_loaded_data(self) -> None:
        """
        Clear any loaded data from the table widget and text edit widget.

        :return: None
        :rtype: None
        """

        # Clearing previous contents
        self.main_window.tableWidget.clear()
        self.main_window.textEdit.clear()

    @log_function_call
    def open_out_file_regular(self, file_path: str) -> None:
        """
        Open and display the contents of a .out file in the table widget.

        :param file_path: The path to the .out file.
        :return: None
        :rtype: None
        """

        self.main_window.textEdit.hide()
        self.main_window.tableWidget.show()
        out_file_instance = InstantaneousPropertiesClass(filename=file_path)
        self.populate_table_widget(data=out_file_instance.data)
        del out_file_instance

    @log_function_call
    def open_trajectories_file_regular(
        self, file_path: str, index: Optional[int] = None
    ) -> None:
        """
        Open and display a trajectories file in the table widget.

        :param file_path: The path to the trajectories file.
        :param index: The index of the trajectory to display, optional.
        :return: None
        :rtype: None
        """

        self.main_window.textEdit.hide()
        self.main_window.tableWidget.show()

        try:
            if self.trajectory_instance is not None:
                del self.trajectory_instance

            self.trajectory_instance = TrajectoriesClass()

            self.trajectory_instance.initialize_trajectory_file(file_path=file_path)

            self.trajectory_instance.next()

            index = index if index is not None else 1
            self.trajectory_instance.go_to(n=index)

            self.populate_table_widget(
                data=self.trajectory_instance.trajectories[-1]["atom_data"],
            )
            # self.trajectory_instance.close_file()
        except:
            QMessageBox.warning(
                self.main_window,
                "Error",
                "Error loading trajectory. End of file reached or file contents not parsable.",
            )

    @log_function_call
    def load_trajectory_from_spinbox(self, index: Optional[int] = None) -> None:
        """
        Load and display trajectory data based on the specified index.

        :param index: The index of the trajectory, optional.
        :return: None
        :rtype: None
        """

        try:
            index = index if index is not None else 1
            self.trajectory_instance.go_to(n=index)

            self.populate_table_widget(
                data=self.trajectory_instance.trajectories[-1]["atom_data"],
            )
        except:
            QMessageBox.warning(
                self.main_window,
                "Error",
                "Error loading trajectory. End of file reached or file contents not parsable.",
            )

    @log_function_call
    def on_pushbutton_trajectory_clicked(self) -> None:
        """
        Handle the event when the 'trajectory' pushbutton is clicked.

        :return: None
        :rtype: None
        """

        index = self.main_window.spinBox_trajectory.value() - 1
        self.load_trajectory_from_spinbox(index=index)

    @log_function_call
    def open_other_file_types(self, file_path: str) -> None:
        """
        Open and display contents of file types other than .out and .lammpstrj in the text edit widget.

        :param file_path: The path to the file.
        :return: None
        :rtype: None
        """

        self.main_window.tableWidget.hide()
        self.main_window.textEdit.show()
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
        self.main_window.textEdit.setText(content)

        # Apply the syntax highlighter to the QTextEdit document
        self.highlighter = LammpsSyntaxHighlighter(self.main_window.textEdit.document())

    @log_function_call
    def populate_table_widget(self, data: Dict[str, List[float]]) -> None:
        """
        Populate the table widget with provided data.

        :param data: The data to populate the table with, structured as a dictionary.
        :return: None
        :rtype: None
        """

        # Assume all lists in data have the same length
        list_length = len(next(iter(data.values())))

        # Configure the table dimensions
        self.main_window.tableWidget.setRowCount(list_length)
        self.main_window.tableWidget.setColumnCount(len(data))

        # Retrieve and set the headers from the keys of the dictionary
        headers = list(data.keys())
        self.main_window.tableWidget.setHorizontalHeaderLabels(headers)

        # No vertical headers in 'regular' mode, assuming row indices are sufficient
        self.main_window.tableWidget.setVerticalHeaderLabels([""] * list_length)

        # Populate the table with data
        for col, header in enumerate(headers):
            for row, value in enumerate(data[header]):
                # Format the number as a string with desired precision
                formatted_value = "{:.4f}".format(value).rstrip("0").rstrip(".")
                item = QTableWidgetItem(formatted_value)
                self.main_window.tableWidget.setItem(row, col, item)

        # Resize columns to fit content
        self.main_window.tableWidget.resizeColumnsToContents()
        self.main_window.tableWidget.resizeRowsToContents()
