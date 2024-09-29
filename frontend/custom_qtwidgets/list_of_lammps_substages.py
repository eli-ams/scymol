from PyQt5.QtGui import QDropEvent
from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import QEvent
from PyQt5.QtCore import Qt
from logging_functions import print_to_log, log_function_call


class ListOfLammpsSubstages(QListWidget):
    """
    A custom QListWidget for managing a list of Lammps substages.

    Attributes:
        main_window: Reference to the main window.
        stages_counter: A dictionary to keep track of the number of occurrences of each substage.

    Methods:
        set_style_sheet(self) -> None:
            Set the stylesheet for the QListWidget.
        dropEvent(self, event: QDropEvent) -> None:
            Handle drop events (reordering or adding new items).
        addItemProgramatically(self, item_text: str) -> None:
            Add an item programmatically to the list with incremented counter.
    """

    @log_function_call
    def __init__(self, *args, **kwargs) -> None:
        """
        Initialize the ListOfLammpsSubstages.

        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        :return: None
        :rtype: None
        """
        super(ListOfLammpsSubstages, self).__init__(*args, **kwargs)
        self.setObjectName("ListOfStagesWidget")
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.main_window = None
        self.stages_counter = {
            "Initialize": 0,
            "Minimize": 0,
            "Velocities": 0,
            "NPT": 0,
            "NVT": 0,
            "NVE": 0,
            "UniaxialDeformation": 0,
        }
        self.set_style_sheet()

    @log_function_call
    def set_style_sheet(self) -> None:
        """
        Set the stylesheet for the QListWidget.

        :return: None
        :rtype: None
        """
        self.setStyleSheet(
            """
            QListWidget {
                background-color: white;
            }
            QListWidget::item {
                border-top: 1px solid black;
                border-bottom: -1px solid black;  /* Negative value for overlap */
                border-left: 1px solid black;
                border-right: 1px solid black;
                padding: 16px; /* make it wider/higher */
                margin-bottom: -1px;  /* Negative value to pull items together */
            }
            QListWidget::item:first-child {
                border-top: 1px solid black;
            }
            QListWidget::item:last-child {
                border-bottom: 1px solid black;
            }
            QListWidget::item:drag {
                border: 2px solid black;
                background-color: #d5e0f0;
            }
        """
        )

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
                # Add sorting or reordering logic here
                if self.main_window:
                    self.main_window.sort_lammps_windows()  # Sort the lammpsWindows dict
            return

        # Check if the source is the same as the target
        if event.source() is self:
            self.main_window.sort_lammps_windows()
            return

        moved_item.setTextAlignment(Qt.AlignCenter)
        self.stages_counter[moved_item.text()] += 1
        moved_item.setText(
            f"{moved_item.text()} {self.stages_counter[moved_item.text()]}"
        )

        # Call showProperties method here
        if self.main_window:
            self.main_window.show_properties(moved_item, show=False)

        self.main_window.sort_lammps_windows()

    @log_function_call
    def add_item_programmatically(self, item_text: str) -> None:
        """
        Add an item programmatically to the list with incremented counter.

        :param item_text: The text of the item to be added.
        :type item_text: str
        :return: None
        :rtype: None
        """
        # Increment the appropriate counter and append it to the item's text
        self.stages_counter[item_text] += 1
        item = QListWidgetItem(f"{item_text} {self.stages_counter[item_text]}")
        item.setTextAlignment(Qt.AlignCenter)
        self.addItem(item)
