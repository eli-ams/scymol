from PyQt5.QtWidgets import (
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QSpinBox,
    QCheckBox,
)
from PyQt5.QtCore import Qt
import scymol.static_functions as static_functions
from scymol.logging_functions import print_to_log, log_function_call


class MixtureTableWidget(QTableWidget):
    """
    A custom widget for managing the mixture table.

    :param main_window: The main application window.
    :type main_window: MainWindow
    :param parent: The parent widget, defaults to None.
    :type parent: QWidget, optional
    """

    @log_function_call
    def __init__(self, main_window, parent=None):
        """
        Initialize the MixtureTableWidget.

        :param main_window: The main application window.
        :type main_window: MainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(MixtureTableWidget, self).__init__(parent)
        self.main_window = main_window
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Name", "Number", "Rotate"])
        for i in range(self.columnCount()):
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        self.main_window.tabWidget.currentChanged.connect(
            self.update_mixture_table_on_tab_change
        )

    @log_function_call
    def update_mixture_table_on_tab_change(self, index: int) -> None:
        """
        Update the mixture table when the current tab changes.

        :param index: The index of the current tab.
        :type index: int
        """
        if index != 1:
            return

        self.setRowCount(0)

        for row in range(self.main_window.tab1.moleculeList.count()):
            item = self.main_window.tab1.moleculeList.item(row)
            name = item.text()
            data = self.main_window.mixture_table[name]
            self.update_mixture_table(name, data["number"], data["rotate"])

    @log_function_call
    def update_mixture_table(self, name: str, number: int, rotate: bool) -> None:
        """
        Update the mixture table with the given data.

        :param name: The name of the molecule.
        :type name: str
        :param number: The number of molecules.
        :type number: int
        :param rotate: Whether to rotate the molecule.
        :type rotate: bool
        """
        row_position = self.rowCount()
        self.insertRow(row_position)
        self.setItem(row_position, 0, QTableWidgetItem(name))
        spin_box = QSpinBox()
        spin_box.setMaximum(9999999)
        spin_box.setValue(number)
        spin_box.valueChanged.connect(
            lambda n, name=name: (
                self.update_number(name, n),
                self.generate_mixture_information(),
            )
        )
        self.setCellWidget(row_position, 1, spin_box)
        rotate_checkbox = QCheckBox("Rotate")
        rotate_checkbox.setChecked(rotate)
        rotate_checkbox.stateChanged.connect(
            lambda state, name=name: self.update_rotate(name, state)
        )
        self.setCellWidget(row_position, 2, rotate_checkbox)
        self.generate_mixture_information()

    @log_function_call
    def update_number(self, name: str, number: int) -> None:
        """
        Update the number of molecules for a given name.

        :param name: The name of the molecule.
        :type name: str
        :param number: The number of molecules.
        :type number: int
        """
        self.main_window.mixture_table[name]["number"] = number

    @log_function_call
    def update_rotate(self, name: str, state: int) -> None:
        """
        Update the rotation state for a given name.

        :param name: The name of the molecule.
        :type name: str
        :param state: The rotation state (0 for unchecked, 2 for checked).
        :type state: int
        """
        self.main_window.mixture_table[name]["rotate"] = state == Qt.Checked

    @log_function_call
    def generate_mixture_information(self) -> None:
        """
        Generate and update the mixture information label.

        This method computes the mixture information based on the current state of the mixture table
        and updates the relevant label in the main application window.

        :return: None
        :rtype: None
        """
        self.main_window.label_mixture_info.setText(
            static_functions.generate_mixture_information(
                mixture_table=self.main_window.mixture_table,
                molecules_objects=self.main_window.molecules_objects,
            )
        )
