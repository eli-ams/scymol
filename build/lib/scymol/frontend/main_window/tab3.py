from PyQt5.QtWidgets import QWidget, QListWidget
from scymol.front2back.data_extractor import DataExtractor
from scymol.frontend.custom_qtwidgets.list_of_stages_widget import ListOfStagesWidget
from typing import Optional
from scymol.logging_functions import print_to_log, log_function_call


class Tab3(QWidget):
    """
    A widget representing the third tab in the main application window.

    This tab manages the workflow stages for the application, allowing users to select and arrange stages.

    :param main_window: The main window of the application.
    :type main_window: QMainWindow
    :param parent: The parent widget, defaults to None.
    :type parent: QWidget, optional
    """

    @log_function_call
    def __init__(
        self, main_window: "MainWindow", parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize Tab3.

        :param main_window: The main window of the application.
        :type main_window: QMainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(Tab3, self).__init__(parent)
        self.data_extractor: Optional[DataExtractor] = None
        self.stages_counter: Optional[dict] = None
        self.selected_stages_widget: Optional[ListOfStagesWidget] = None
        self.available_stages_widget: Optional[QListWidget] = None
        self.main_window = main_window
        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets within Tab3.

        :return: None
        :rtype: None
        """
        self.available_stages_widget = QListWidget()
        self.available_stages_widget.setObjectName("available_stages_widget")
        self.available_stages_widget.setDragEnabled(True)
        self.available_stages_widget.addItems(["LAMMPS Stage", "Set Cell"])

        self.selected_stages_widget = ListOfStagesWidget(self)
        self.stages_counter = self.selected_stages_widget.stages_counter

        self.data_extractor = DataExtractor(self.selected_stages_widget)

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts within Tab3.

        :return: None
        :rtype: None
        """
        self.main_window.horizontalLayout_3.addWidget(self.available_stages_widget)
        self.main_window.horizontalLayout_3.addWidget(self.selected_stages_widget)

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals within Tab3.

        :return: None
        :rtype: None
        """
        pass
