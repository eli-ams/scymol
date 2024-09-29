import matplotlib.pyplot as plt
import numpy as np
from PyQt5.QtGui import QContextMenuEvent
from PyQt5.QtWidgets import (
    QTableWidgetItem,
    QTableWidget,
    QMenu,
    QDialog,
    QVBoxLayout,
    QLabel,
    QWidget,
)
from scipy import stats
from typing import Union, Dict, Tuple, Optional
from logging_functions import print_to_log, log_function_call


class CustomTableWidget(QTableWidget):
    @log_function_call
    def __init__(
        self, data: Dict[str, Dict[str, float]], parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize the CustomTableWidget with the given data.

        The table is populated with the data where each key in the dictionary represents a column,
        and the associated dictionary values are the row entries for that column.

        :param data: A dictionary where keys are column headers and values are dictionaries
                     containing row data for each column.
        :param parent: The parent widget, optional.
        :return: None
        :rtype: None
        """

        super(CustomTableWidget, self).__init__(parent)

        # Set table dimensions
        self.setColumnCount(len(data))
        self.setRowCount(len(next(iter(data.values()))))

        # Set the headers for the table
        self.setHorizontalHeaderLabels(data.keys())
        self.setVerticalHeaderLabels(
            [str(index) for index in range(len(next(iter(data.values()))))]
        )

        # Populate the table with data
        for col_index, (key, values) in enumerate(data.items()):
            for row_index, (statistic, value) in enumerate(values.items()):
                item = QTableWidgetItem(f"{value:.4f}")
                self.setItem(row_index, col_index, item)

        # Resize columns to fit contents
        self.resizeColumnsToContents()

        # Allow for the selection of columns
        self.setSelectionBehavior(QTableWidget.SelectColumns)
        self.setSelectionMode(QTableWidget.ExtendedSelection)

    @log_function_call
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        Handle the right-click context menu event to provide options like plotting and statistics.

        Depending on the number of selected columns, different actions such as plotting
        or computing statistics are offered.

        :param event: The context menu event.
        :return: None
        :rtype: None
        """

        context_menu = QMenu(self)

        selected_columns = list(set(index.column() for index in self.selectedIndexes()))

        # Initialize potential actions to None
        compute_stats_action = None
        plot_1_vs_2_action = None
        plot_2_vs_1_action = None

        if len(selected_columns) == 1:
            # Add a submenu for statistics
            compute_stats_action = context_menu.addAction("Statistics...")
        elif len(selected_columns) == 2:
            # Existing functionality to plot columns against each other
            plot_1_vs_2_action = context_menu.addAction("Plot 1 vs 2")
            plot_2_vs_1_action = context_menu.addAction("Plot 2 vs 1")
        else:
            context_menu.addAction(
                "Select one or two columns to perform actions"
            ).setEnabled(False)

        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        # Check if the action is to compute statistics
        if action == compute_stats_action:
            self.display_statistics(selected_columns[0])
        elif len(selected_columns) == 2:
            if action == plot_1_vs_2_action:
                self.plot_columns(selected_columns[0], selected_columns[1])
            elif action == plot_2_vs_1_action:
                self.plot_columns(selected_columns[1], selected_columns[0])

    @log_function_call
    def plot_columns(self, x_col: int, y_col: int) -> None:
        """
        Plot the data of two selected columns against each other in a scatter plot.

        This method is triggered when the user selects the plot option from the context menu.
        It generates a scatter plot using matplotlib, with appropriate labels and an aspect ratio.

        :param x_col: The index of the column to be plotted on the x-axis.
        :param y_col: The index of the column to be plotted on the y-axis.
        :return: None
        :rtype: None
        """

        data_x = [float(self.item(row, x_col).text()) for row in range(self.rowCount())]
        data_y = [float(self.item(row, y_col).text()) for row in range(self.rowCount())]

        plt.style.use(
            "bmh"
        )  # Using a style that is typically good for scientific papers

        plt.figure(figsize=(10, 8))
        plt.scatter(
            data_x, data_y, color="black", s=50, edgecolor="none"
        )  # s is the size of markers

        # Adding grid lines
        plt.grid(True, which="major", linestyle="--", linewidth=0.5, color="black")

        # Labeling the axes with appropriate size
        plt.xlabel(self.horizontalHeaderItem(x_col).text(), fontsize=10)
        plt.ylabel(self.horizontalHeaderItem(y_col).text(), fontsize=10)

        # Adding title with appropriate size
        plt.title(
            f"Scatter Plot: {self.horizontalHeaderItem(x_col).text()} vs {self.horizontalHeaderItem(y_col).text()}",
            fontsize=12,
        )

        # Setting tick parameters
        plt.tick_params(axis="both", which="major", labelsize=12)

        # Calculate the data range for both x and y
        x_range = max(data_x) - min(data_x)
        y_range = max(data_y) - min(data_y)

        try:
            # Set the aspect ratio to 1:1 based on the data range
            plt.gca().set_aspect(x_range / y_range, adjustable="box")
        except Exception:
            pass

        # Optional: Customizing the legend
        plt.legend(loc="best", fontsize=8)

        plt.tight_layout()  # Adjusting the plot to ensure everything fits without overlapping
        plt.show()

    @log_function_call
    def display_mean(self, col: int) -> None:
        """
        Display a dialog showing the mean value of the selected column.

        :param col: The index of the column for which the mean value is to be calculated.
        :return: None
        :rtype: None
        """

        mean_value = self.compute_mean(col)
        dialog = QDialog(self)
        dialog.setWindowTitle("Mean Value")
        layout = QVBoxLayout()
        label = QLabel(f"The mean is: {mean_value:.4f}")
        layout.addWidget(label)
        dialog.setLayout(layout)
        dialog.exec_()

    @log_function_call
    def compute_mean(self, col: int) -> float:
        """
        Compute and return the mean value of the selected column.

        :param col: The index of the column for which the mean value is to be calculated.
        :return: The mean value of the column.
        :rtype: float
        """

        data = [float(self.item(row, col).text()) for row in range(self.rowCount())]
        return sum(data) / len(data) if data else 0

    @log_function_call
    def display_statistics(self, col: int) -> None:
        """
        Display a dialog with various statistical measures for the selected column.

        The statistics include average, standard deviation, standard error, confidence interval,
        coefficient of variation, maximum, and minimum values.

        :param col: The index of the column for which statistics are to be calculated.
        :return: None
        :rtype: None
        """

        stats = self.compute_statistics(col)
        dialog = QDialog(self)
        dialog.setWindowTitle("Statistics")
        layout = QVBoxLayout()

        for stat_name, value in stats.items():
            if isinstance(
                value, tuple
            ):  # Assuming confidence interval is the only tuple
                text = f"{stat_name}: {value[0]:.4g} to {value[1]:.4g}"
            else:
                text = f"{stat_name}: {value:.4g}"
            layout.addWidget(QLabel(text))

        dialog.setLayout(layout)
        dialog.exec_()

    @log_function_call
    def compute_statistics(
        self, col: int
    ) -> Dict[str, Union[float, Tuple[float, float]]]:
        """
        Compute various statistical measures for the selected column.

        This method calculates statistics such as average, standard deviation, standard error,
        confidence interval, coefficient of variation, maximum, and minimum values.

        :param col: The index of the column for which statistics are to be calculated.
        :return: A dictionary containing the calculated statistical measures.
        :rtype: Dict[str, Union[float, Tuple[float, float]]]
        """

        data_array = np.array(
            [float(self.item(row, col).text()) for row in range(self.rowCount())]
        )
        statistics = {
            "Average": np.mean(data_array),
            "Standard Deviation": np.std(data_array, ddof=1),
            "Standard Error": stats.sem(data_array),
            "Confidence Interval": stats.t.interval(
                0.95,
                len(data_array) - 1,
                loc=np.mean(data_array),
                scale=stats.sem(data_array),
            ),
            "Coefficient of Variation": (
                np.std(data_array, ddof=1) / np.mean(data_array)
            )
            * 100,
            "Max Value": np.max(data_array),
            "Min Value": np.min(data_array),
        }
        return statistics
