import importlib

from PyQt5 import uic
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QListWidget, QMenu, QAction, QMainWindow, QListWidgetItem
from scymol.frontend.custom_qtwidgets.list_of_lammps_substages import (
    ListOfLammpsSubstages,
)
from scymol.frontend.lammps_flowchart_window.dialog_windows.initialize import (
    LammpsInitializeSubstage,
)
from scymol.frontend.lammps_flowchart_window.dialog_windows.minimize import (
    LammpsMinimizeSubstage,
)
from scymol.frontend.lammps_flowchart_window.dialog_windows.velocities import (
    LammpsVelocitiesSubstage,
)
from scymol.frontend.lammps_flowchart_window.dialog_windows.nvt import LammpsNvtSubstage
from scymol.frontend.lammps_flowchart_window.dialog_windows.npt import LammpsNptSubstage
from scymol.frontend.lammps_flowchart_window.dialog_windows.nve import LammpsNveSubstage
from scymol.frontend.lammps_flowchart_window.dialog_windows.uniaxial_deformation import (
    LammpsUniaxialDeformation,
)


# Resolve the full path to the .ui file
ui_path = importlib.resources.files("scymol.frontend.uis").joinpath("pop_window.ui")

# Open the .ui file as a file object and load it with uic.loadUiType
with ui_path.open("r") as f:
    Ui_FlowChartWindow, _ = uic.loadUiType(f)


class LammpsFlowChartWindow(QMainWindow):
    """
    Class representing the window for creating a flowchart of Lammps simulation stages.

    Attributes:
        ui (Ui_FlowChartWindow): The user interface for this window.
        available_lammps_substages (QListWidget): List widget for available Lammps stages.
        mainListWidget (ListOfLammpsSubstages): List widget for the flowchart of Lammps stages.
        currentRowIndex (str): The currently selected row index.
        itemTypeToWindowClass (dict): Map of item types to window classes.
        lammpsWindows (dict): Dictionary to hold LammpsSubstage instances by item text.
    """

    def __init__(self, stageName: str, parent=None):
        """
        Initialize the LammpsFlowChartWindow.

        Args:
            stageName (str): The name of the Lammps stage.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super(LammpsFlowChartWindow, self).__init__(parent)
        self.ui = Ui_FlowChartWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(stageName)
        layout = self.ui.horizontalLayout
        self.available_lammps_substages = QListWidget()
        self.available_lammps_substages.setDragEnabled(True)
        self.available_lammps_substages.addItems(
            [
                "Initialize",
                "Minimize",
                "Velocities",
                "NPT",
                "NVT",
                "NVE",
                "UniaxialDeformation",
            ]
        )

        layout.addWidget(self.available_lammps_substages)
        self.mainListWidget = ListOfLammpsSubstages()
        self.mainListWidget.main_window = self
        self.mainListWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mainListWidget.customContextMenuRequested.connect(self.show_context_menu)
        self.ui.actionUniaxial_compression.triggered.connect(
            self.library_add_uniaxial_compression
        )
        self.ui.actionHeat_cycle.triggered.connect(self.library_add_heat_cycle)

        self.ui.actionSimple_minimization.triggered.connect(
            self.library_simple_minimization
        )
        self.ui.actionDensity_equilibration.triggered.connect(
            self.library_density_equilibration
        )

        layout.addWidget(self.mainListWidget)
        self.mainListWidget.itemDoubleClicked.connect(self.show_properties)
        self.currentRowIndex = None  # To keep track of the currently selected row index
        # Map of item types to the class of the window that should be displayed
        self.itemTypeToWindowClass = {
            "Initialize": LammpsInitializeSubstage,
            "Minimize": LammpsMinimizeSubstage,
            "Velocities": LammpsVelocitiesSubstage,
            "NPT": LammpsNptSubstage,
            "NVT": LammpsNvtSubstage,
            "NVE": LammpsNveSubstage,
            "UniaxialDeformation": LammpsUniaxialDeformation,
            "default": LammpsInitializeSubstage,
        }
        self.lammpsWindows = (
            {}
        )  # Dictionary to hold LammpsSubstage instances by item text

        self.add_stages_programmatically()

    def show_properties(self, item: QListWidgetItem, show: bool = True) -> None:
        """
        Show properties for the selected item.

        This method displays the properties window for the selected item in the mainListWidget.
        It hides any previously shown properties window if there was one.

        Args:
            item (QListWidgetItem): The selected item.
            show (bool, optional): Whether to show the properties window. Defaults to True.

        Returns:
            None
        """
        item_text = item.text()

        if self.currentRowIndex in self.lammpsWindows:
            self.lammpsWindows[self.currentRowIndex].hide_window()

        self.currentRowIndex = item_text

        # Fetch item type to decide which UI to show
        item_type = item_text

        if item_text not in self.lammpsWindows:
            # Use the correct UI window based on item type
            window_class = self.itemTypeToWindowClass[
                "default"
            ]  # default to standard window
            for key in self.itemTypeToWindowClass.keys():
                if key in item_type:
                    window_class = self.itemTypeToWindowClass[key]
                    break

            self.lammpsWindows[item_text] = window_class()
        if show:
            self.lammpsWindows[item_text].show()

    def show_context_menu(self, pos: QPoint) -> None:
        """
        Show a context menu with options to delete the current item or delete all items.

        This method displays a context menu with options to delete the currently selected item
        or delete all items from the mainListWidget.

        Args:
            pos (QPoint): The position where the context menu should be displayed.

        Returns:
            None
        """
        menu = QMenu(self)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_item)
        menu.addAction(delete_action)

        delete_all_action = QAction("Delete all", self)
        delete_all_action.triggered.connect(self.delete_all_items)
        menu.addAction(delete_all_action)

        menu.exec_(self.mainListWidget.mapToGlobal(pos))

    def delete_item(self) -> None:
        """
        Delete the currently selected item from the mainListWidget and its associated LammpsWindow.

        This method removes the currently selected item from the mainListWidget,
        hides the associated LammpsWindow, and updates the current selection if available.

        Returns:
            None
        """
        current_item = self.mainListWidget.currentItem()
        if current_item is None:
            return

        current_row = self.mainListWidget.currentRow()
        item_text = current_item.text()

        if item_text in self.lammpsWindows:
            self.lammpsWindows.pop(item_text).hide_window()

        self.mainListWidget.takeItem(
            current_row
        )  # This line removes the item from the list

        if self.mainListWidget.count() > 0:
            next_row = min(
                self.mainListWidget.currentRow(), self.mainListWidget.count() - 1
            )
            new_item = self.mainListWidget.item(next_row)
            self.mainListWidget.setCurrentItem(new_item)
        else:
            self.currentRowIndex = None

        self.sort_lammps_windows()

    def delete_all_items(self) -> None:
        """
        Delete all items from the mainListWidget and associated LammpsWindows.

        This method removes all items from the mainListWidget, hides associated LammpsWindows,
        resets counters, and clears the currentRowIndex.

        Returns:
            None
        """
        keys = list(
            self.lammpsWindows.keys()
        )  # Get a list of all keys in the dictionary
        for key in keys:
            self.lammpsWindows.pop(key).hide_window()  # Remove each window and hide it

        self.mainListWidget.clear()  # Remove all items from the mainListWidget
        self.currentRowIndex = (
            None  # Reset the currentRowIndex as no item is selected now
        )
        self.mainListWidget.stages_counter = {
            key: 0 for key in self.mainListWidget.stages_counter
        }  # Resetting counter

    def add_item_programmatically(self, item_text: str) -> None:
        """
        Add an item programmatically to the mainListWidget and perform necessary updates.

        This method adds an item with the specified text to the mainListWidget.
        It also updates properties display and sorts the LammpsWindows dictionary.

        Args:
            item_text (str): The text of the item to be added.

        Returns:
            None
        """
        self.mainListWidget.add_item_programmatically(item_text)
        self.show_properties(
            self.mainListWidget.item(self.mainListWidget.count() - 1), show=False
        )
        self.sort_lammps_windows()

    def add_stages_programmatically(self, list_of_stages: list = None) -> None:
        """
        Add stages programmatically to the mainListWidget and sort LammpsWindows.

        This method adds stages to the mainListWidget based on the provided list
        of stage names. It also sorts the LammpsWindows dictionary to match the order
        in the mainListWidget.

        Args:
            list_of_stages (list): A list of stage names to be added programmatically.

        Returns:
            None
        """
        if list_of_stages:
            for stage in list_of_stages:
                self.add_item_programmatically(item_text=stage)
        self.sort_lammps_windows()

    def sort_lammps_windows(self) -> None:
        """
        Sort the LammpsWindows dictionary based on the order in the mainListWidget.

        This method iterates through the items in the mainListWidget and reorders
        the LammpsWindows dictionary to match the order in the list.

        Args:
            None

        Returns:
            None
        """
        sorted_dict = {}
        for i in range(self.mainListWidget.count()):
            item = self.mainListWidget.item(i)
            key = item.text()
            if key in self.lammpsWindows:
                sorted_dict[key] = self.lammpsWindows[key]
        self.lammpsWindows = sorted_dict

    def library_add_uniaxial_compression(self) -> None:
        """
        Configure the simulation stages for uniaxial compression.

        This method sets up the simulation stages for uniaxial compression, including
        initialization, minimization, velocities, NVT, UniaxialDeformation, NPT, NVT,
        NVE, and final minimization stages.

        Args:
            None

        Returns:
            None
        """
        # Clear existing items in the list
        self.delete_all_items()

        # Add simulation stages programmatically
        stages = [
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
        self.add_stages_programmatically(stages)

        # # Set z-boundaries for the initialization stage
        # self.lammpsWindows["Initialize 1"].ui.combobox_zboundaries.setCurrentIndex(1)

    def library_add_heat_cycle(self) -> None:
        """
        Configure the simulation stages for a heat cycle.

        This method sets up the simulation stages for a heat cycle, including
        initialization, minimization, and multiple NVT stages to simulate heating.

        Args:
            None

        Returns:
            None
        """
        # Clear existing items in the list
        self.delete_all_items()

        # Add simulation stages programmatically
        stages = ["Initialize", "Minimize", "Velocities", "NVT", "NVT", "NVT"]
        self.add_stages_programmatically(stages)

        # Set temperature values for NVT stages
        initial_temperature = 473.15
        final_temperature = 473.15

        self.lammpsWindows["NVT 1"].ui.spinbox_finaltemperature.setValue(
            final_temperature
        )
        self.lammpsWindows["NVT 2"].ui.spinbox_initialtemperature.setValue(
            initial_temperature
        )
        self.lammpsWindows["NVT 2"].ui.spinbox_finaltemperature.setValue(
            final_temperature
        )
        self.lammpsWindows["NVT 3"].ui.spinbox_initialtemperature.setValue(
            initial_temperature
        )

    def library_simple_minimization(self) -> None:
        """
        Configure the simulation stages for a simple minimization.

        This method sets up the simulation stages for a simple energy minimization
        without any additional equilibration or dynamics stages.

        Args:
            None

        Returns:
            None
        """
        # Clear existing items in the list
        self.delete_all_items()

        # Add simulation stages programmatically
        stages = ["Initialize", "Minimize"]
        self.add_stages_programmatically(stages)

    def library_density_equilibration(self) -> None:
        """
        Configure the simulation stages for density equilibration.

        This method sets up the simulation stages for density equilibration
        with specific parameters and values.

        Args:
            None

        Returns:
            None
        """
        # Clear existing items in the list
        self.delete_all_items()

        # Add simulation stages programmatically
        stages = [
            "Initialize",
            "Minimize",
            "Velocities",
            "NVT",
            "NPT",
            "NPT",
            "Minimize",
        ]
        self.add_stages_programmatically(stages)

        # Set specific values for the number of runs (nrun) in NVT and NPT stages
        self.lammpsWindows["NVT 1"].ui.spinbox_nrun.setValue(50_000)
        self.lammpsWindows["NPT 1"].ui.spinbox_nrun.setValue(250_000)
        self.lammpsWindows["NPT 2"].ui.spinbox_nrun.setValue(250_000)

        # Set the rhoaverage in the second NPT stage
        self.lammpsWindows["NPT 2"].ui.combobox_rhoaverage.setCurrentIndex(1)
