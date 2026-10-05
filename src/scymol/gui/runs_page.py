from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..models import RunRecord, ScymolProject
from .base import StagePage, configure_table
from .lammps_setup import (
    lammps_command_template,
    lammps_status_text,
    load_lammps_configuration,
)
from .process_dialog import ProcessDialog


class RunsPage(StagePage):
    recordsChanged = QtCore.Signal()
    resultsRequested = QtCore.Signal(str)
    configureLammpsRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(
            "4 · Run",
            "Prepare independent simulation folders from the current structure and protocol, then select one to run.",
            "Prepare new simulation",
            parent,
        )
        self.compact_header()
        self.use_workspace_layout()

        prepare_box = QtWidgets.QGroupBox("Prepare new simulation")
        prepare_layout = QtWidgets.QVBoxLayout(prepare_box)
        prepare_row = QtWidgets.QHBoxLayout()
        self.simulation_name = QtWidgets.QLineEdit()
        self.simulation_name.setPlaceholderText("Optional name")
        self.simulation_name.setMaxLength(80)
        self.run_button.setText("Prepare new simulation")
        self.run_button.setMinimumWidth(190)
        prepare_row.addWidget(QtWidgets.QLabel("Name"))
        prepare_row.addWidget(self.simulation_name, 1)
        prepare_row.addWidget(self.run_button)
        prepare_layout.addLayout(prepare_row)
        prepare_hint = QtWidgets.QLabel(
            "Creates a new, independent folder from the current structure and protocol. "
            "If no name is entered, Scymol uses <number>_<datestamp>."
        )
        prepare_hint.setObjectName("note")
        prepare_hint.setWordWrap(True)
        prepare_layout.addWidget(prepare_hint)
        self.layout.addWidget(prepare_box)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        prepared_box = QtWidgets.QGroupBox("Prepared simulations")
        prepared_layout = QtWidgets.QVBoxLayout(prepared_box)
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Simulation", "Prepared", "Status", "Duration", "Scripts"]
        )
        configure_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        prepared_layout.addWidget(self.table)
        splitter.addWidget(prepared_box)

        details = QtWidgets.QGroupBox("Selected simulation")
        details.setMinimumHeight(360)
        details_layout = QtWidgets.QVBoxLayout(details)
        summary_row = QtWidgets.QHBoxLayout()
        self.selected_summary = QtWidgets.QLabel("No run selected")
        self.selected_summary.setObjectName("sectionTitle")
        self.output_path = QtWidgets.QLabel("")
        self.output_path.setObjectName("note")
        self.output_path.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        summary_row.addWidget(self.selected_summary)
        summary_row.addWidget(self.output_path, 1)
        details_layout.addLayout(summary_row)

        queue_row = QtWidgets.QHBoxLayout()
        self.queue_label = QtWidgets.QLabel("Queue idle")
        self.queue_progress = QtWidgets.QProgressBar()
        self.queue_progress.setTextVisible(True)
        self.queue_progress.setRange(0, 1)
        self.queue_progress.setValue(0)
        queue_row.addWidget(self.queue_label)
        queue_row.addWidget(self.queue_progress, 1)
        details_layout.addLayout(queue_row)

        actions = QtWidgets.QHBoxLayout()
        self.run_selected_button = QtWidgets.QPushButton("Run selected")
        self.run_selected_button.setObjectName("primaryButton")
        self.retry_button = QtWidgets.QPushButton("Retry")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.open_button = QtWidgets.QPushButton("Open folder")
        self.view_results_button = QtWidgets.QPushButton("View results")
        actions.addWidget(self.run_selected_button)
        actions.addWidget(self.retry_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        actions.addWidget(self.open_button)
        actions.addWidget(self.view_results_button)
        details_layout.addLayout(actions)

        self.execution_panel = QtWidgets.QGroupBox("Execution settings")
        execution_grid = QtWidgets.QGridLayout(self.execution_panel)
        execution_status_row = QtWidgets.QHBoxLayout()
        execution_status_row.setContentsMargins(0, 0, 0, 0)
        self.execution_status = QtWidgets.QLabel()
        self.execution_status.setObjectName("stageStatus")
        self.execution_status.setWordWrap(True)
        self.configure_lammps_button = QtWidgets.QPushButton("Configure…")
        execution_status_row.addWidget(self.execution_status, 1)
        execution_status_row.addWidget(self.configure_lammps_button)
        self.script_choice = QtWidgets.QComboBox()
        self.command = QtWidgets.QLineEdit('lmp -in "{script}"')
        self.command.setPlaceholderText('mpiexec -np 8 lmp -in "{script}"')
        self.command.setToolTip(
            "Available placeholders: {script}, {script_path}, and {output_dir}."
        )
        lammps_label = QtWidgets.QLabel("LAMMPS")
        script_label = QtWidgets.QLabel("Script")
        command_label = QtWidgets.QLabel("Command")
        for label in (lammps_label, script_label, command_label):
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
        execution_grid.addWidget(lammps_label, 0, 0)
        execution_grid.addLayout(execution_status_row, 0, 1)
        execution_grid.addWidget(script_label, 0, 2)
        execution_grid.addWidget(self.script_choice, 0, 3)
        execution_grid.addWidget(command_label, 1, 0)
        execution_grid.addWidget(self.command, 1, 1, 1, 3)
        execution_grid.setColumnStretch(1, 2)
        execution_grid.setColumnStretch(3, 2)
        details_layout.addWidget(self.execution_panel)

        self.detail = QtWidgets.QPlainTextEdit()
        self.detail.setObjectName("console")
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Run details and process output appear here.")
        self.detail.setMinimumHeight(250)
        details_layout.addWidget(self.detail, 1)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([260, 540])
        self.layout.addWidget(splitter, 1)

        self.table.currentCellChanged.connect(self._selection_changed)
        self.open_button.clicked.connect(self.open_selected)
        self.view_results_button.clicked.connect(self.view_selected_results)
        self.run_selected_button.clicked.connect(self.run_selected)
        self.retry_button.clicked.connect(self.run_selected)
        self.cancel_button.clicked.connect(self.cancel)
        self.configure_lammps_button.clicked.connect(self.configureLammpsRequested)
        self.simulation_name.returnPressed.connect(self.run_button.click)

        self.records: list[RunRecord] = []
        self.queue: list[tuple[int, str]] = []
        self.queue_total = 0
        self.queue_done = 0
        self.queue_failed = 0
        self.active_row = -1
        self.elapsed = QtCore.QElapsedTimer()
        self.duration_timer = QtCore.QTimer(self)
        self.duration_timer.setInterval(500)
        self.duration_timer.timeout.connect(self._update_elapsed)
        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self.process_dialog: ProcessDialog | None = None
        self.project_name = "Scymol project"
        self.project_path = ""
        self.refresh_execution_configuration()
        self._update_action_state()

    def refresh_execution_configuration(self):
        configuration = load_lammps_configuration()
        available = configuration.available
        self.execution_status.setText(lammps_status_text(configuration))
        self.execution_status.setProperty("state", "complete" if available else "pending")
        self.execution_status.style().unpolish(self.execution_status)
        self.execution_status.style().polish(self.execution_status)
        self.configure_lammps_button.setText("Reconfigure…" if available else "Configure…")
        if available:
            self.command.setText(lammps_command_template(configuration))

    def load_project(self, project: ScymolProject):
        self.project_name = project.name
        self.project_path = str(project.root)
        self.set_records(project.runs)

    def set_records(self, records: list[RunRecord]):
        self.records = records
        self.table.setRowCount(len(records))
        for row in range(len(records)):
            self._update_record_row(row)
        if records:
            self.table.selectRow(len(records) - 1)
            completed = sum(record.status == "Complete" for record in records)
            failed = sum(record.status == "Failed" for record in records)
            prepared = sum(record.status == "Prepared" for record in records)
            detail = (
                f"{len(records)} simulation folder(s) · {prepared} prepared"
                f" · {completed} complete"
            )
            if failed:
                detail += f" · {failed} failed"
            self.set_status("Simulation prepared", "complete", detail)
        else:
            self.detail.setPlainText(
                "Prepare a simulation folder from the current structure and protocol."
            )
            self.set_status("Pending", "pending", "Simulation input has not been prepared")
        self._update_action_state()

    def _selection_changed(self, row: int, *_):
        self.script_choice.clear()
        if not (0 <= row < len(self.records)):
            self.selected_summary.setText("No run selected")
            self.output_path.clear()
            self._update_action_state()
            return
        record = self.records[row]
        for script in record.scripts:
            self.script_choice.addItem(Path(script).name, script)
        self.selected_summary.setText(
            f"{self._record_label(record)}  ·  {record.status}"
        )
        self.output_path.setText(Path(record.output_dir).name or record.output_dir)
        self.output_path.setToolTip(record.output_dir)
        if self.process.state() == QtCore.QProcess.ProcessState.NotRunning:
            scripts = "\n".join(f"  • {Path(path).name}" for path in record.scripts) or "  • None"
            message = f"\nMessage: {record.message}" if record.message else ""
            self.detail.setPlainText(
                f"Status: {record.status}\n"
                f"Duration: {self._format_duration(record.duration_seconds)}\n"
                f"Output: {record.output_dir}\nScripts:\n{scripts}{message}"
            )
        self._update_action_state()

    def _selected_record(self):
        row = self.table.currentRow()
        return self.records[row] if 0 <= row < len(self.records) else None

    def requested_simulation_name(self) -> str:
        return self.simulation_name.text().strip()

    def preparation_succeeded(self):
        self.simulation_name.clear()

    def open_selected(self):
        record = self._selected_record()
        if record:
            path = Path(record.output_dir)
            if path.exists():
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def view_selected_results(self):
        record = self._selected_record()
        if record:
            self.resultsRequested.emit(record.output_dir)

    def run_selected(self):
        row = self.table.currentRow()
        script = self.script_choice.currentData()
        if 0 <= row < len(self.records) and script:
            self.queue = [(row, script)]
            self._begin_queue(1)

    def _begin_queue(self, total: int):
        self.queue_total = total
        self.queue_done = 0
        self.queue_failed = 0
        self.queue_progress.setRange(0, total)
        self.queue_progress.setValue(0)
        self.queue_label.setText(f"Queue 0/{total}")
        self._start_next()

    def _start_next(self):
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            return
        if not self.queue:
            self.active_row = -1
            self.duration_timer.stop()
            self._set_busy(False)
            if self.queue_total:
                self.queue_label.setText(f"Queue complete · {self.queue_done}/{self.queue_total}")
                if self.queue_failed:
                    self.set_status(
                        "Finished with failures",
                        "failed",
                        f"{self.queue_failed} of {self.queue_total} run(s) failed",
                    )
                else:
                    self.set_status("Complete", "complete", "Selected run queue finished")
            self.recordsChanged.emit()
            return
        self.active_row, script = self.queue.pop(0)
        record = self.records[self.active_row]
        record.status = "Running"
        record.message = ""
        record.duration_seconds = 0.0
        self._update_record_row(self.active_row)
        self.table.selectRow(self.active_row)
        self.detail.clear()
        command = self.command.text().strip().format(
            script=Path(script).name,
            script_path=str(Path(script)),
            output_dir=record.output_dir,
        )
        if not command:
            record.status = "Failed"
            record.message = "No LAMMPS command configured."
            self._update_record_row(self.active_row)
            self.queue.clear()
            self.set_status("Failed", "failed", record.message)
            return
        self.detail.appendPlainText(f"> {command}\n")
        self.process_dialog = ProcessDialog(
            f"LAMMPS · {self._record_label(record)}",
            self.project_name,
            record.output_dir,
            self.window(),
            allow_cancel=True,
        )
        self.process_dialog.cancelRequested.connect(self.cancel)
        self.process_dialog.destroyed.connect(self._run_dialog_destroyed)
        self.process_dialog.append_log(f"Script: {script}")
        self.process_dialog.append_log(f"Command: {command}")
        self.process_dialog.show()
        self.process_dialog.raise_()
        self.process_dialog.activateWindow()
        self.process.setWorkingDirectory(record.output_dir)
        self._set_busy(True)
        self.set_status("Running", "running", record.name)
        self.elapsed.start()
        self.duration_timer.start()
        self.process.startCommand(command)

    def _update_elapsed(self):
        if 0 <= self.active_row < len(self.records) and self.elapsed.isValid():
            self.records[self.active_row].duration_seconds = self.elapsed.elapsed() / 1000.0
            item = self.table.item(self.active_row, 3)
            if item:
                item.setText(self._format_duration(self.records[self.active_row].duration_seconds))

    def _read_output(self):
        text = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        self.detail.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.detail.insertPlainText(text)
        self.detail.ensureCursorVisible()
        if self.process_dialog is not None:
            self.process_dialog.append_output(text)

    def _finished(self, exit_code: int, exit_status):
        if not (0 <= self.active_row < len(self.records)):
            return
        self._update_elapsed()
        self.duration_timer.stop()
        record = self.records[self.active_row]
        success = exit_code == 0 and exit_status == QtCore.QProcess.ExitStatus.NormalExit
        record.status = "Complete" if success else "Failed"
        if not success:
            self.queue_failed += 1
        record.message = f"Process exited with code {exit_code}."
        self.detail.appendPlainText(f"\n{record.message}")
        if self.process_dialog is not None:
            self.process_dialog.append_log(record.message)
            self.process_dialog.finish_run(success)
        self._update_record_row(self.active_row)
        self.queue_done += 1
        self.queue_progress.setValue(self.queue_done)
        self.queue_label.setText(f"Queue {self.queue_done}/{self.queue_total}")
        self.recordsChanged.emit()
        QtCore.QTimer.singleShot(0, self._start_next)

    def _process_error(self, error):
        if 0 <= self.active_row < len(self.records) and error == QtCore.QProcess.ProcessError.FailedToStart:
            self._update_elapsed()
            self.duration_timer.stop()
            record = self.records[self.active_row]
            record.status = "Failed"
            record.message = self.process.errorString()
            self.detail.appendPlainText(f"\n{record.message}")
            if self.process_dialog is not None:
                self.process_dialog.append_log(f"ERROR: {record.message}")
                self.process_dialog.finish_run(False)
            self._update_record_row(self.active_row)
            self.queue.clear()
            self.queue_done += 1
            self.queue_failed += 1
            self.queue_progress.setValue(self.queue_done)
            self.queue_label.setText(
                f"Queue stopped · {self.queue_done}/{self.queue_total} · failed to start"
            )
            self._set_busy(False)
            self.set_status("Failed", "failed", record.message)
            self.recordsChanged.emit()

    def cancel(self):
        self.queue.clear()
        if self.process.state() != QtCore.QProcess.ProcessState.NotRunning:
            if self.process_dialog is not None:
                self.process_dialog.append_log("Cancellation requested…")
                self.process_dialog.cancel_button.setEnabled(False)
            self.process.kill()

    def _run_dialog_destroyed(self, *_):
        self.process_dialog = None

    def _set_busy(self, busy: bool):
        record = self._selected_record()
        has_script = bool(self.script_choice.currentData())
        self.run_button.setEnabled(not busy)
        self.simulation_name.setEnabled(not busy)
        self.run_selected_button.setEnabled(not busy and has_script)
        self.retry_button.setEnabled(
            not busy and record is not None and record.status == "Failed" and has_script
        )
        self.cancel_button.setEnabled(busy)
        self.open_button.setEnabled(not busy and record is not None)
        self.view_results_button.setEnabled(not busy and record is not None)

    def _update_action_state(self):
        self._set_busy(
            self.process.state() != QtCore.QProcess.ProcessState.NotRunning
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if not seconds:
            return "—"
        if seconds < 60:
            return f"{seconds:.1f} s"
        minutes, remainder = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:d}h {minutes:02d}m" if hours else f"{minutes:d}m {remainder:02d}s"

    def _update_record_row(self, row: int):
        if not (0 <= row < len(self.records)):
            return
        record = self.records[row]
        values = [
            self._record_label(record),
            record.created_at.replace("T", " "),
            record.status,
            self._format_duration(record.duration_seconds),
            str(len(record.scripts)),
        ]
        status_colors = {
            "Prepared": ("○", "#6f7b80", "#f1f3f3"),
            "Generated": ("○", "#6f7b80", "#f1f3f3"),
            "Running": ("●", "#2f747c", "#dceff0"),
            "Complete": ("✓", "#2f747c", "#e6f2f1"),
            "Failed": ("!", "#a33f3f", "#f8e7e7"),
        }
        for column, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(value)
            if column == 2:
                symbol, foreground, background = status_colors.get(
                    record.status, ("○", "#6f7b80", "#f1f3f3")
                )
                item.setText(f"{symbol}  {record.status}")
                item.setForeground(QtGui.QColor(foreground))
                item.setBackground(QtGui.QColor(background))
            if column == 0:
                item.setToolTip(record.output_dir)
            self.table.setItem(row, column, item)

    @staticmethod
    def _record_label(record: RunRecord) -> str:
        if record.sequence > 0 and not record.name.startswith(f"{record.sequence}_"):
            return f"{record.sequence} · {record.name}"
        return record.name
