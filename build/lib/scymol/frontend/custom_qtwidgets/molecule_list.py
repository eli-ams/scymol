from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDropEvent, QContextMenuEvent
from PyQt5.QtWidgets import QListWidget, QMenu, QListWidgetItem, QWidget
from typing import Optional
from scymol.logging_functions import print_to_log, log_function_call


class MoleculesList(QListWidget):
    """
    Custom QListWidget for managing a list of molecules.
    """

    @log_function_call
    def __init__(self, *args, **kwargs):
        """
        Initialize the MoleculesList widget.

        :param args: Variable length argument list.
        :param kwargs: Arbitrary keyword arguments.
        """
        super(MoleculesList, self).__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.main_window = None

    @log_function_call
    def set_parent(
        self,
        parent: Optional[QWidget] = None,
        main_window: Optional["MainWindow"] = None,
    ) -> None:
        """
        Set the parent and main window for the MoleculesList widget.

        :param parent: The parent widget.
        :type parent: QWidget, optional
        :param main_window: The main window widget.
        :type main_window: MainWindow, optional
        :return: None
        :rtype: None
        """
        super(MoleculesList, self).setParent(parent)
        self.main_window = main_window

    @log_function_call
    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle the drop event when molecules are dragged and dropped.

        :param event: The drop event.
        :type event: QDropEvent
        :return: None
        :rtype: None
        """
        super().dropEvent(event)

        # check if the source is the same as the target
        if event.source() is self:
            return

        # get dropped item
        dropped_item: QListWidgetItem = self.item(self.count() - 1)

        # set data to item
        dropped_item.setData(Qt.UserRole, "")

    @log_function_call
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """
        Handle the context menu event.

        :param event: The context menu event.
        :type event: QContextMenuEvent
        :return: None
        :rtype: None
        """
        menu = QMenu(self)
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_item)
        menu.exec_(event.globalPos())

    @log_function_call
    def delete_selected_item(self) -> None:
        """
        Delete the selected items from the MoleculesList.

        :return: None
        :rtype: None
        """
        selected_items = self.selectedItems()
        for item in selected_items:
            selected_items_text = item.text()
            row = self.row(item)
            self.takeItem(row)

        # Update information display
        new_selected_items = self.selectedItems()
        if new_selected_items:
            self.main_window.tab1.display_info(
                new_selected_items[0]
            )  # Show info of first newly selected item
        else:
            self.main_window.moleculeInfo.clear()  # Clear the text box if no items left
            self.main_window.moleculeInfo.setEnabled(
                False
            )  # Disable the text box if no items left
            self.main_window.tab1.image_viewer.clear_image()

        # Delete molecule object from molecules_objects:
        self.delete_molecule(molecule_name=selected_items_text)

    @log_function_call
    def delete_molecule(self, molecule_name: str) -> None:
        """
        Delete a molecule from the molecules_objects dictionary.

        :param molecule_name: The name of the molecule to delete.
        :type molecule_name: str
        :return: None
        :rtype: None
        """
        if molecule_name in self.main_window.molecules_objects:
            del self.main_window.molecules_objects[molecule_name]
            del self.main_window.mixture_table[molecule_name]
