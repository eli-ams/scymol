from PyQt5.QtWidgets import QWidget
from frontend.custom_qtwidgets.mixture_table_widget import MixtureTableWidget
from typing import Optional
from logging_functions import print_to_log, log_function_call


class Tab2(QWidget):
    """
    A widget representing the second tab in the main application window.

    This tab manages a mixture table for the application.

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
        Initialize Tab2.

        :param main_window: The main window of the application.
        :type main_window: QMainWindow
        :param parent: The parent widget, defaults to None.
        :type parent: QWidget, optional
        """
        super(Tab2, self).__init__(parent)
        self.main_window = main_window
        self.mixture_table = None
        self.initialize_widgets()
        self.initialize_layouts()
        self.connect_signals()

    @log_function_call
    def initialize_widgets(self) -> None:
        """
        Initialize widgets within Tab2.

        :return: None
        :rtype: None
        """
        self.mixture_table = MixtureTableWidget(self.main_window)

    @log_function_call
    def initialize_layouts(self) -> None:
        """
        Initialize layouts within Tab2.

        :return: None
        :rtype: None
        """
        self.main_window.verticalLayout_28.addWidget(self.mixture_table)

    @log_function_call
    def connect_signals(self) -> None:
        """
        Connect signals within Tab2.

        :return: None
        :rtype: None
        """
        pass
