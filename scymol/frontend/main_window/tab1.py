from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QListWidgetItem, QWidget

from scymol.frontend.custom_qtwidgets.image_viewer import ImageViewer
from scymol.frontend.custom_qtwidgets.molecule_list import MoleculesList
from scymol.logging_functions import print_to_log, log_function_call


class Tab1(QWidget):
    """
    A widget representing the first tab in the main application window.

    This tab manages a list of molecules and displays information and images for each molecule.

    :param main_window: The main window of the application.
    :type main_window: QMainWindow
    :param parent: The parent widget, defaults to None.
    :type parent: QWidget, optional
    """

    @log_function_call
    def __init__(self, main_window, parent=None):
        """
        Initialize Tab1.

        :param main_window: The main window of the application.
        :type main_window: QMainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(Tab1, self).__init__(parent)
        self.main_window = main_window

        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets within Tab1.

        :return: None
        :rtype: None
        """
        # Initialize molecules list
        self.moleculeList = MoleculesList(self)
        self.moleculeList.set_parent(self, main_window=self.main_window)

        # Initialize Image Viewer
        self.image_viewer = ImageViewer()

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts within Tab1.

        :return: None
        :rtype: None
        """
        self.main_window.top_layout.insertWidget(1, self.moleculeList)
        self.main_window.verticalLayout.addWidget(self.image_viewer)

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals within Tab1.

        :return: None
        :rtype: None
        """
        self.moleculeList.itemClicked.connect(self.display_info)

    @log_function_call
    def add_molecule(self, name: str, number: int = 50, rotate: bool = True) -> None:
        """
        Add a molecule to the list and display its information.

        :param name: The name of the molecule.
        :type name: str
        :param number: The number of molecules, defaults to 50.
        :type number: int, optional
        :param rotate: Whether the molecule should be rotated, defaults to True.
        :type rotate: bool, optional
        :return: None
        :rtype: None
        """
        item = QListWidgetItem(name)
        self.moleculeList.addItem(item)
        self.moleculeList.setCurrentItem(item)
        self.display_info(name)
        self.main_window.moleculeInfo.setEnabled(True)
        self.main_window.tab2.mixture_table.update_mixture_table(name, 0, True)
        self.main_window.mixture_table[name] = {"number": number, "rotate": rotate}

    @log_function_call
    def display_info(self, name: str) -> None:
        """
        Display information about a selected molecule.

        :param name: The name of the molecule or the QListWidgetItem representing the molecule.
        :type name: Union[str, QListWidgetItem]
        :return: None
        :rtype: None
        """
        if isinstance(name, QListWidgetItem):
            name = name.text()
        self.main_window.moleculeInfo.setText(
            f"Source: ({self.main_window.molecules_objects[name].source_type}) "
            f"{self.main_window.molecules_objects[name].source}\n"
            f"Number of atoms: {self.main_window.molecules_objects[name].nbr_atoms}\n"
            f"Chemical formula: {self.main_window.molecules_objects[name].mol_formula}\n"
            f"Molecular Mass (Da): {self.main_window.molecules_objects[name].mol_weight: .2f}"
        )

        # Assuming `generate_image` in your `Molecule` class produces a QImage
        # stored in self.image, use ImageViewer's `loadQImage` method to display it.
        qimage = QImage.fromData(
            self.main_window.molecules_objects[name].image, "PNG"
        )  # Make sure the format matches what you saved
        self.image_viewer.load_qimage(qimage)
