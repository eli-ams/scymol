from PyQt5.QtWidgets import (
    QTextEdit,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
)
from typing import Any, Dict

from scymol.frontend.lammps_flowchart_window.lammps_flowchart_window import (
    LammpsFlowChartWindow,
)
from scymol.logging_functions import print_to_log, log_function_call


class DataExtractor:
    """
    A class for extracting widget data from a GUI and organizing it into a dictionary.

    :ivar stages_list: The list of stages containing the widgets to extract data from.
    :vartype stages_list: Any
    :ivar data: The extracted data organized into a dictionary.
    :vartype data: Dict[str, Any]
    """

    @log_function_call
    def __init__(self, stages_list: Any) -> None:
        """
        Initialize a DataExtractor instance.

        :param stages_list: The list of stages containing the widgets to extract data from.
        :type stages_list: Any
        """
        self.stages_list = stages_list
        self.data: Dict[str, Any] = {}

    def extract_widget_data(self, parent: Any, data_dict: Dict[str, Any]) -> None:
        """
        Recursively extract data from widgets and populate the data_dict.

        :param parent: The parent widget to start extracting data from.
        :type parent: Any
        :param data_dict: The dictionary to populate with extracted data.
        :type data_dict: Dict[str, Any]
        """
        for child in parent.children():
            if isinstance(child, QTextEdit):
                data_dict[child.objectName()] = child.toPlainText()
            elif isinstance(child, QComboBox):
                data_dict[child.objectName()] = child.currentText()
            elif isinstance(child, QLineEdit):
                data_dict[child.objectName()] = child.text()
            elif isinstance(child, QCheckBox):
                data_dict[child.objectName()] = child.isChecked()
            elif isinstance(child, QDoubleSpinBox):
                data_dict[child.objectName()] = child.value()
            elif isinstance(child, QSpinBox):
                data_dict[child.objectName()] = child.value()
            else:
                self.extract_widget_data(child, data_dict)

    @log_function_call
    def get_simulation_inputs(self) -> Dict[str, Any]:
        """
        Retrieve and structure the simulation inputs data from the GUI widgets.

        :return: The extracted data organized into a dictionary.
        :rtype: Dict[str, Any]
        """
        self.data = {}

        for fc_key, fc_window in self.stages_list.substage_windows.items():
            fc_data_dict = {}
            self.extract_widget_data(fc_window, fc_data_dict)

            print(f"Processing window {fc_key} / {fc_window}...")
            if isinstance(fc_window, LammpsFlowChartWindow):
                lammps_data_dict = {}
                for lammps_key, lammps_window in fc_window.lammpsWindows.items():
                    lammps_window_data_dict = {}
                    self.extract_widget_data(lammps_window, lammps_window_data_dict)
                    print("        >", lammps_window_data_dict)
                    lammps_data_dict[lammps_key] = lammps_window_data_dict
                fc_data_dict["lammpsWindows"] = lammps_data_dict
            else:
                raise Exception(
                    f"Stage window named {fc_key} (obj: {fc_window}) is not a recognized instance."
                )

            self.data[fc_key] = fc_data_dict

        return self.data
