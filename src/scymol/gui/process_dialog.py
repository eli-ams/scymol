from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import traceback
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets


class TaskWorker(QtCore.QObject):
    """Run one Python task away from Qt's GUI thread."""

    logReceived = QtCore.Signal(str)
    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str, str)
    finished = QtCore.Signal()

    def __init__(self, task: Callable[[Callable[[str], None]], Any]):
        super().__init__()
        self._task = task

    @QtCore.Slot()
    def run(self):
        try:
            result = self._task(self.logReceived.emit)
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc())
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class ProcessDialog(QtWidgets.QDialog):
    """Application-modal, persistent monitor for one background task."""

    cancelRequested = QtCore.Signal()

    def __init__(
        self,
        title: str,
        project_name: str,
        project_path: str,
        parent=None,
        allow_cancel: bool = False,
    ):
        super().__init__(parent)
        self._task_title = title
        self._running = True
        self._status_text = "Running"
        self.setWindowTitle(f"Running · {title}")
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(860, 600)
        self.setMinimumSize(640, 420)

        root = QtWidgets.QVBoxLayout(self)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("pageTitle")
        context = QtWidgets.QLabel(f"{project_name}  ·  {project_path}")
        context.setObjectName("pageDescription")
        context.setWordWrap(True)
        root.addWidget(heading)
        root.addWidget(context)

        progress_row = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("Starting…")
        self.status_label.setObjectName("sectionTitle")
        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        progress_row.addWidget(self.status_label)
        progress_row.addWidget(self.progress, 1)
        root.addLayout(progress_row)

        self.console = QtWidgets.QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(8000)
        root.addWidget(self.console, 1)

        actions = QtWidgets.QHBoxLayout()
        self.copy_button = QtWidgets.QPushButton("Copy log")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setVisible(allow_cancel)
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setEnabled(False)
        actions.addWidget(self.copy_button)
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.close_button)
        root.addLayout(actions)

        self.copy_button.clicked.connect(self._copy_log)
        self.cancel_button.clicked.connect(self.cancelRequested.emit)
        self.close_button.clicked.connect(self.close)
        self.elapsed = QtCore.QElapsedTimer()
        self.elapsed.start()
        self.elapsed_timer = QtCore.QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._update_elapsed)
        self.elapsed_timer.start()
        self._update_elapsed()

    @property
    def running(self) -> bool:
        return self._running

    @QtCore.Slot(str)
    def append_log(self, message: str):
        if not message:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        lines = str(message).rstrip().splitlines() or [""]
        rendered = "\n".join(
            f"[{timestamp}] {line}" if index == 0 else f"           {line}"
            for index, line in enumerate(lines)
        )
        self.console.appendPlainText(rendered)
        self.console.ensureCursorVisible()

    @QtCore.Slot(str)
    def append_output(self, message: str):
        """Append already-formatted process output without delaying or timestamping it."""
        if not message:
            return
        cursor = self.console.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        cursor.insertText(str(message))
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def finish_run(self, success: bool):
        self._running = False
        self.elapsed_timer.stop()
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if success else 0)
        self._status_text = "Completed" if success else "Failed"
        self.setWindowTitle(f"{self._status_text} · {self._task_title}")
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.close_button.setDefault(True)
        self._update_elapsed()
        self.raise_()
        self.activateWindow()

    def append_traceback(self, detail: str):
        if detail:
            self.console.appendPlainText("\nTechnical details:\n" + detail.rstrip())
            self.console.ensureCursorVisible()

    def _update_elapsed(self):
        seconds = max(0, self.elapsed.elapsed() // 1000)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed_text = (
            f"{hours:d}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes:02d}:{seconds:02d}"
        )
        self.status_label.setText(f"{self._status_text}  ·  {elapsed_text}")

    def _copy_log(self):
        QtWidgets.QApplication.clipboard().setText(self.console.toPlainText())

    def closeEvent(self, event: QtGui.QCloseEvent):
        if self._running:
            event.ignore()
            return
        super().closeEvent(event)
