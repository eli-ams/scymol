from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QDropEvent
from PyQt5.QtWidgets import QListWidget, QMenu, QAction, QListWidgetItem
from scymol.frontend.lammps_flowchart_window.lammps_flowchart_window import (
    LammpsFlowChartWindow,
)
from scymol.frontend.dialog_windows.set_cell_window import SetCellWindow
from typing import List
from scymol.logging_functions import print_to_log, log_function_call


class ListOfStagesWidget(QListWidget):
    """
    A custom QListWidget for managing a list of stages in the main window.
    ...
    """

    addStageSignal = pyqtSignal(str)

    @log_function_call
    def __init__(self, main_window, *args, **kwargs) -> None:
        """
        Initialize the ListOfStagesWidget.

        :param main_window: Reference to the main window.
        :type main_window: MainWindow
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: None
        :rtype: None
        """
        super(ListOfStagesWidget, self).__init__(*args, **kwargs)
        self.setObjectName("ListOfStagesWidget")
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.main_window = main_window
        self.stages_counter = {"LAMMPS Stage": 0, "Set Cell": 0}
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemDoubleClicked.connect(self.open_flowchart_window)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.substage_windows = {}
        self.set_style_sheet()
        self.item_to_stage_mapping = {
            "LAMMPS Stage": LammpsFlowChartWindow,
            "Set Cell": SetCellWindow,
        }

        self.initialize_default_compression_simulation_stages()

    @log_function_call
    def set_style_sheet(self) -> None:
        """
        Set the stylesheet for the QListWidget.

        :return: None
        :rtype: None
        """
        self.setStyleSheet(
            """
            QListWidget#ListOfStagesWidget {
                background-color: white;
            }
            QListWidget#ListOfStagesWidget::item {
                border-top: 1px solid black;
                border-bottom: -1px solid black;  /* Negative value for overlap */
                border-left: 1px solid black;
                border-right: 1px solid black;
                padding: 16px; /* make it wider/higher */
                margin-bottom: -1px;  /* Negative value to pull items together */
            }
            QListWidget#ListOfStagesWidget::item:first-child {
                border-top: 1px solid black;
            }
            QListWidget#ListOfStagesWidget::item:last-child {
                border-bottom: 1px solid black;
            }
            QListWidget#ListOfStagesWidget::item:drag {
                border: 2px solid black;
                background-color: #f1f1f1; 
            }
        """
        )

    @log_function_call
    def sort_substage_windows(self) -> None:
        """
        Sort the substage windows dictionary.

        :return: None
        :rtype: None
        """
        # Only works for Python 3.7+, as the order of insertion in dictionaries must be preserved.
        sorted_dict = {}
        for i in range(self.count()):
            item = self.item(i)
            key = item.text()
            sorted_dict[key] = self.substage_windows[key]
        self.substage_windows = sorted_dict

    @log_function_call
    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop events (reordering or adding new items).

        :param event: The drop event.
        :type event: QDropEvent
        :return: None
        :rtype: None
        """
        # Store the initial positions of all items before the drop operation
        initial_positions = {self.item(i).text(): i for i in range(self.count())}

        # Call the parent class dropEvent to actually perform the operation
        super().dropEvent(event)

        # Now check the new positions of all items to find the moved one
        moved_item = None
        for i in range(self.count()):
            item = self.item(i)
            if initial_positions.get(item.text()) is None:
                moved_item = item
                break

        if moved_item is None:
            # Check if the source is the same as the target
            if event.source() is self:
                self.sort_substage_windows()
            return

        self.add_flowchart_stage(moved_item)

    @log_function_call
    def delete_stage(self) -> None:
        """
        Delete a stage.

        :return: None
        :rtype: None
        """
        currentRow = self.currentRow()
        item = self.item(currentRow)
        self.takeItem(currentRow)
        if item is not None:
            stageNameKey = item.text()
            if stageNameKey in self.substage_windows:
                del self.substage_windows[stageNameKey]
        self.sort_substage_windows()

    @log_function_call
    def show_context_menu(self, pos: QPoint) -> None:
        """
        Show the context menu for stage items.

        :param pos: The position where the context menu is requested.
        :type pos: QPoint
        :return: None
        :rtype: None
        """
        menu = QMenu(self)
        deleteAction = QAction("Delete stage", self)
        deleteAction.triggered.connect(self.delete_stage)
        menu.addAction(deleteAction)
        menu.exec_(self.mapToGlobal(pos))

    @log_function_call
    def open_flowchart_window(self, item: QListWidgetItem) -> None:
        """
        Open the corresponding substage window when an item is double-clicked.

        :param item: The item that was double-clicked.
        :type item: QListWidgetItem
        :return: None
        :rtype: None
        """
        stageName = item.text()
        for stageType, WindowClass in self.item_to_stage_mapping.items():
            if stageType in stageName:
                self.substage_windows[stageName].show()
                return

    @log_function_call
    def add_flowchart_stage(self, item: QListWidgetItem) -> None:
        """
        Add a flowchart stage item.

        :param item: The item to be added.
        :type item: QListWidgetItem
        :return: None
        :rtype: None
        """
        item_text = item.text()
        self.stages_counter[item_text] += 1
        stage_name = f"{item_text} {self.stages_counter[item_text]}"
        item.setText(stage_name)
        item.setTextAlignment(Qt.AlignCenter)  # Centering the text
        self.addItem(item)

        window_class = self.item_to_stage_mapping.get(item_text, LammpsFlowChartWindow)
        # Automatically create an instance and store it
        self.substage_windows[item.text()] = window_class(item.text(), self)

    @log_function_call
    def count_lammps_substages(self) -> List[int]:
        """
        Count the number of LAMMPS substages in each stage.

        This method traverses through the substage windows and counts the number of substages
        present in each LAMMPS stage.

        :return: A list of integers, each representing the count of substages in a LAMMPS stage.
        :rtype: List[int]
        """
        count = []
        for key in self.substage_windows.keys():
            count.append(self.substage_windows[key].mainListWidget.count())
        return count

    @log_function_call
    def add_lammps_stage(self) -> None:
        """
        Add a LAMMPS stage item.

        :return: None
        :rtype: None
        """
        # Create a QListWidgetItem
        item = QListWidgetItem("LAMMPS Stage")

        # Standardize the way of adding stages
        self.add_flowchart_stage(item)

    @log_function_call
    def add_set_cell(self) -> None:
        """
        Add a Set Cell stage item.

        :return: None
        :rtype: None
        """
        # Create a QListWidgetItem
        item = QListWidgetItem("Set Cell")

        # Standardize the way of adding stages
        self.add_flowchart_stage(item)

    @log_function_call
    def initialize_default_compression_simulation_stages(self) -> None:
        """
        Initialize default stages for compression simulation.

        :return: None
        :rtype: None
        """
        self.add_lammps_stage()
        self.substage_windows[
            f'LAMMPS Stage {self.stages_counter["LAMMPS Stage"]}'
        ].add_stages_programmatically(
            [
                "Initialize",
                "Minimize",
                "Velocities",
                "NVT",
                "UniaxialDeformation",
                "NPT",
                "NVT",
                "NVE",
                "Minimize",
            ]
        )
        self.sort_substage_windows()
