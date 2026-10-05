from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class StagePage(QtWidgets.QWidget):
    runRequested = QtCore.Signal()
    changed = QtCore.Signal()
    continueRequested = QtCore.Signal()
    statusChanged = QtCore.Signal(str, str, str)

    def __init__(self, title: str, description: str, run_text: str | None = None, parent=None):
        super().__init__(parent)
        self.outer = QtWidgets.QVBoxLayout(self)
        self.outer.setContentsMargins(16, 14, 16, 12)
        self.heading = QtWidgets.QLabel(title)
        self.heading.setObjectName("pageTitle")
        self.description = QtWidgets.QLabel(description)
        self.description.setObjectName("pageDescription")
        self.description.setWordWrap(True)
        self.outer.addWidget(self.heading)
        self.outer.addWidget(self.description)

        self.content_scroll = QtWidgets.QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.content = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(self.content)
        self.layout.setContentsMargins(0, 8, 0, 8)
        self.content_scroll.setWidget(self.content)
        self.outer.addWidget(self.content_scroll, 1)

        self.run_bar = QtWidgets.QFrame()
        self.run_bar.setObjectName("runBar")
        run_layout = QtWidgets.QHBoxLayout(self.run_bar)
        run_layout.setContentsMargins(10, 8, 10, 4)
        self.status = QtWidgets.QLabel("Pending")
        self.status.setObjectName("stageStatus")
        self.status.setProperty("state", "pending")
        self.output = QtWidgets.QLabel("")
        self.output.setWordWrap(True)
        run_layout.addWidget(self.status)
        run_layout.addWidget(self.output, 1)
        self.run_button = None
        if run_text:
            self.run_button = QtWidgets.QPushButton(run_text)
            self.run_button.setObjectName("primaryButton")
            self.run_button.clicked.connect(self.runRequested.emit)
            run_layout.addWidget(self.run_button)
        self.continue_button = QtWidgets.QPushButton("Continue")
        self.continue_button.setObjectName("secondaryButton")
        self.continue_button.setVisible(False)
        self.continue_button.clicked.connect(self.continueRequested.emit)
        run_layout.addWidget(self.continue_button)
        self._continue_enabled = False
        self.outer.addWidget(self.run_bar)

    def set_status(self, text: str, state: str = "pending", output: str = ""):
        self.status.setText(text)
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.output.setText(output)
        self.continue_button.setVisible(self._continue_enabled and state == "complete")
        self.statusChanged.emit(text, state, output)

    def set_running(self, running: bool):
        if self.run_button:
            self.run_button.setEnabled(not running)
        if running:
            self.set_status("Running", "running")

    def configure_continue(self, text: str = "Continue"):
        self._continue_enabled = True
        self.continue_button.setText(text)
        self.continue_button.setVisible(self.status.property("state") == "complete")

    def compact_header(self):
        """Let the tab name carry the stage title and keep only useful context."""
        self.heading.setVisible(False)
        self.outer.setContentsMargins(14, 8, 14, 10)
        self.layout.setContentsMargins(0, 4, 0, 4)

    def use_workspace_layout(self):
        """Replace the outer page scroller with a full-height workspace."""
        if self.content_scroll is None:
            return
        index = self.outer.indexOf(self.content_scroll)
        self.content_scroll.takeWidget()
        self.outer.removeWidget(self.content_scroll)
        self.outer.insertWidget(index, self.content, 1)
        self.content_scroll.deleteLater()
        self.content_scroll = None


def configure_table(table: QtWidgets.QTableWidget):
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
