from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path
import re
import shutil
import sys
import tempfile

from PySide6 import QtCore, QtGui, QtWidgets


SETTINGS_GROUP = "lammps_execution"
DEFAULT_LOCAL_ONLY = sys.platform.startswith("win")
SMOKE_SUCCESS = "SCYMOL_SMOKE_TEST_OK"
SMOKE_STAGE_DIRECTORIES = (
    "stages/01_initialization",
    "stages/02_minimization",
    "stages/03_velocities",
    "stages/04_nvt",
)


@dataclass(frozen=True)
class LammpsConfiguration:
    lammps_path: str = ""
    mpi_path: str = ""
    processes: int = 2
    local_only: bool = DEFAULT_LOCAL_ONLY
    validated: bool = False
    version: str = ""
    validated_at: str = ""

    @property
    def uses_mpi(self) -> bool:
        return bool(self.mpi_path)

    @property
    def available(self) -> bool:
        if not self.validated or not Path(self.lammps_path).is_file():
            return False
        return not self.uses_mpi or Path(self.mpi_path).is_file()


def load_lammps_configuration() -> LammpsConfiguration:
    settings = QtCore.QSettings()
    settings.beginGroup(SETTINGS_GROUP)
    configuration = LammpsConfiguration(
        lammps_path=str(settings.value("lammps_path", "") or ""),
        mpi_path=str(settings.value("mpi_path", "") or ""),
        processes=max(1, int(settings.value("processes", 2) or 2)),
        local_only=str(
            settings.value("local_only", "true" if DEFAULT_LOCAL_ONLY else "false")
        ).lower() in {
            "1", "true", "yes"
        },
        validated=str(settings.value("validated", "false")).lower() in {
            "1", "true", "yes"
        },
        version=str(settings.value("version", "") or ""),
        validated_at=str(settings.value("validated_at", "") or ""),
    )
    settings.endGroup()
    return configuration


def save_lammps_configuration(configuration: LammpsConfiguration):
    settings = QtCore.QSettings()
    settings.beginGroup(SETTINGS_GROUP)
    settings.setValue("lammps_path", configuration.lammps_path)
    settings.setValue("mpi_path", configuration.mpi_path)
    settings.setValue("processes", configuration.processes)
    settings.setValue("local_only", configuration.local_only)
    settings.setValue("validated", configuration.validated)
    settings.setValue("version", configuration.version)
    settings.setValue("validated_at", configuration.validated_at)
    settings.endGroup()
    settings.sync()


def discover_lammps_executables() -> tuple[str, str]:
    lammps = next(
        (
            path
            for name in ("lmp", "lmp_mpi", "lammps", "lmp_serial")
            if (path := shutil.which(name))
        ),
        "",
    )
    mpi = next(
        (
            path
            for name in ("mpiexec", "mpirun")
            if (path := shutil.which(name))
        ),
        "",
    )
    return lammps, mpi


def lammps_command_template(configuration: LammpsConfiguration) -> str:
    lammps = _quote(configuration.lammps_path)
    if configuration.uses_mpi:
        local_only = " -localonly" if configuration.local_only else ""
        return (
            f"{_quote(configuration.mpi_path)}{local_only} "
            f"-n {configuration.processes} "
            f'{lammps} -in "{{script}}"'
        )
    return f'{lammps} -in "{{script}}"'


def lammps_status_text(configuration: LammpsConfiguration | None = None) -> str:
    configuration = configuration or load_lammps_configuration()
    if configuration.available:
        version = configuration.version or Path(configuration.lammps_path).name
        mode = f"MPI ×{configuration.processes}" if configuration.uses_mpi else "serial"
        if configuration.uses_mpi and configuration.local_only:
            mode += " · local only"
        return f"Ready · {version} · {mode}"
    if configuration.validated:
        return "Configuration missing · one or more saved executables moved"
    return "Not configured · execution remains optional"


def _quote(value: str) -> str:
    return f'"{str(value).replace(chr(34), "")}"'


def _resolve_executable(value: str) -> str:
    candidate = Path(value.strip().strip('"'))
    if candidate.is_file():
        return str(candidate.resolve())
    discovered = shutil.which(value.strip())
    return str(Path(discovered).resolve()) if discovered else ""


class LammpsSetupDialog(QtWidgets.QDialog):
    """Discover, smoke-test, and persist the global LAMMPS execution command."""

    configurationChanged = QtCore.Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LAMMPS execution setup")
        self.setModal(True)
        self.resize(760, 590)
        self._test_active = False
        self._timed_out = False
        self._smoke_directory: Path | None = None
        self._captured_output = ""
        self.validated_configuration: LammpsConfiguration | None = None

        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Configure LAMMPS execution")
        title.setObjectName("pageTitle")
        description = QtWidgets.QLabel(
            "Scymol validates the selected executables with a short packaged benzene "
            "minimization and NVT run. The temporary smoke-test folder is deleted when "
            "the test finishes, whether it succeeds or fails."
        )
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        self.status = QtWidgets.QLabel()
        self.status.setObjectName("stageStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        form = QtWidgets.QFormLayout()
        self.lammps_path = QtWidgets.QLineEdit()
        self.lammps_path.setPlaceholderText("lmp.exe or lmp")
        self.lammps_browse = QtWidgets.QPushButton("Browse…")
        lammps_row = QtWidgets.QHBoxLayout()
        lammps_row.addWidget(self.lammps_path, 1)
        lammps_row.addWidget(self.lammps_browse)
        form.addRow("LAMMPS executable", lammps_row)

        self.use_mpi = QtWidgets.QCheckBox("Launch through MPI")
        self.use_mpi.setChecked(True)
        form.addRow("Parallel execution", self.use_mpi)
        self.mpi_path = QtWidgets.QLineEdit()
        self.mpi_path.setPlaceholderText("mpiexec.exe, mpiexec, or mpirun")
        self.mpi_browse = QtWidgets.QPushButton("Browse…")
        mpi_row = QtWidgets.QHBoxLayout()
        mpi_row.addWidget(self.mpi_path, 1)
        mpi_row.addWidget(self.mpi_browse)
        form.addRow("MPI launcher", mpi_row)
        self.processes = QtWidgets.QSpinBox()
        self.processes.setRange(1, 1024)
        self.processes.setValue(2)
        form.addRow("MPI processes", self.processes)
        self.local_only = QtWidgets.QCheckBox(
            "Restrict MPI ranks to this computer (-localonly)"
        )
        self.local_only.setChecked(DEFAULT_LOCAL_ONLY)
        self.local_only.setToolTip(
            "Recommended for Microsoft MPI. Disable this if your MPI launcher does "
            "not recognize -localonly."
        )
        form.addRow("MPI scope", self.local_only)
        layout.addLayout(form)

        controls = QtWidgets.QHBoxLayout()
        self.detect_button = QtWidgets.QPushButton("Auto-detect")
        self.test_button = QtWidgets.QPushButton("Test and save")
        self.test_button.setObjectName("primaryButton")
        self.close_button = QtWidgets.QPushButton("Continue without changing")
        controls.addWidget(self.detect_button)
        controls.addStretch()
        controls.addWidget(self.close_button)
        controls.addWidget(self.test_button)
        layout.addLayout(controls)

        self.log = QtWidgets.QPlainTextEdit()
        self.log.setObjectName("console")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Smoke-test output will appear here.")
        layout.addWidget(self.log, 1)

        self.process = QtCore.QProcess(self)
        self.process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.timeout = QtCore.QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.setInterval(30_000)
        self.timeout.timeout.connect(self._test_timed_out)

        self.detect_button.clicked.connect(self.auto_detect)
        self.test_button.clicked.connect(self.test_configuration)
        self.close_button.clicked.connect(self.reject)
        self.lammps_browse.clicked.connect(lambda: self._browse_executable(self.lammps_path))
        self.mpi_browse.clicked.connect(lambda: self._browse_executable(self.mpi_path))
        self.use_mpi.toggled.connect(self._mpi_toggled)

        saved = load_lammps_configuration()
        if saved.lammps_path:
            self.lammps_path.setText(saved.lammps_path)
            self.mpi_path.setText(saved.mpi_path)
            self.processes.setValue(saved.processes)
            self.local_only.setChecked(saved.local_only)
            self.use_mpi.setChecked(saved.uses_mpi)
        if not saved.available:
            self.auto_detect(report=True)
        self._mpi_toggled(self.use_mpi.isChecked())
        if saved.available:
            self._set_status(lammps_status_text(saved), "complete")

    def auto_detect(self, _checked=False, report: bool = True):
        lammps, mpi = discover_lammps_executables()
        if lammps:
            self.lammps_path.setText(lammps)
        if mpi:
            self.mpi_path.setText(mpi)
            self.use_mpi.setChecked(True)
        if report:
            if lammps and mpi:
                self._set_status("Found LAMMPS and an MPI launcher. Run the smoke test to verify them.", "running")
            elif lammps:
                self._set_status("Found LAMMPS, but no MPI launcher. Browse to MPI or disable MPI.", "pending")
            else:
                self._set_status("LAMMPS was not found on PATH. Select its executable manually.", "failed")

    def _browse_executable(self, editor: QtWidgets.QLineEdit):
        filename, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select executable",
            editor.text(),
            "Executables (*.exe);;All files (*)",
        )
        if filename:
            editor.setText(filename)

    def _mpi_toggled(self, enabled: bool):
        self.mpi_path.setEnabled(enabled)
        self.mpi_browse.setEnabled(enabled)
        self.processes.setEnabled(enabled)
        self.local_only.setEnabled(enabled)

    def test_configuration(self):
        if self._test_active:
            return
        lammps = _resolve_executable(self.lammps_path.text())
        mpi = _resolve_executable(self.mpi_path.text()) if self.use_mpi.isChecked() else ""
        if not lammps:
            self._set_status("Select a valid LAMMPS executable.", "failed")
            return
        if self.use_mpi.isChecked() and not mpi:
            self._set_status("Select a valid MPI launcher or disable MPI execution.", "failed")
            return
        self.lammps_path.setText(lammps)
        if mpi:
            self.mpi_path.setText(mpi)

        self._captured_output = ""
        self.log.clear()
        self._timed_out = False
        try:
            self._prepare_smoke_directory()
        except Exception as exc:
            self._cleanup_smoke_directory()
            self._set_status(f"Could not prepare the smoke test: {exc}", "failed")
            return

        arguments = []
        program = lammps
        if mpi:
            program = mpi
            if self.local_only.isChecked():
                arguments.append("-localonly")
            arguments.extend(["-n", str(self.processes.value()), lammps])
        arguments.extend(["-in", "smoke_test.in"])
        self.log.appendPlainText(
            "Command: " + " ".join([_quote(program), *(_quote(item) if " " in item else item for item in arguments)])
        )
        self.log.appendPlainText(f"Working directory: {self._smoke_directory}\n")
        self.process.setWorkingDirectory(str(self._smoke_directory))
        self._set_testing(True)
        self._set_status("Running the packaged Scymol smoke test…", "running")
        self.timeout.start()
        self.process.start(program, arguments)

    def _prepare_smoke_directory(self):
        self._cleanup_smoke_directory()
        self._smoke_directory = Path(tempfile.mkdtemp(prefix="scymol_lammps_smoke_"))
        package_root = resources.files("scymol").joinpath("resources", "lammps_smoke")
        for name in ("smoke_test.in", "structure.data"):
            (self._smoke_directory / name).write_bytes(package_root.joinpath(name).read_bytes())
        for relative in SMOKE_STAGE_DIRECTORIES:
            (self._smoke_directory / relative).mkdir(parents=True, exist_ok=True)

    def _read_output(self):
        text = bytes(self.process.readAllStandardOutput()).decode(errors="replace")
        if not text:
            return
        self._captured_output += text
        self.log.moveCursor(QtGui.QTextCursor.MoveOperation.End)
        self.log.insertPlainText(text)
        self.log.ensureCursorVisible()

    def _process_finished(self, exit_code: int, exit_status):
        if not self._test_active:
            return
        self._read_output()
        normal = exit_status == QtCore.QProcess.ExitStatus.NormalExit
        final_structure = (
            self._smoke_directory / "stages/04_nvt/structure.data"
            if self._smoke_directory else None
        )
        success = bool(
            not self._timed_out
            and normal
            and exit_code == 0
            and SMOKE_SUCCESS in self._captured_output
            and "ERROR:" not in self._captured_output
            and final_structure is not None
            and final_structure.is_file()
            and final_structure.stat().st_size > 0
        )
        try:
            if success:
                version_match = re.search(r"LAMMPS\s+\([^)]+\)", self._captured_output)
                version = version_match.group(0) if version_match else "LAMMPS"
                configuration = LammpsConfiguration(
                    lammps_path=str(Path(self.lammps_path.text()).resolve()),
                    mpi_path=(
                        str(Path(self.mpi_path.text()).resolve())
                        if self.use_mpi.isChecked() else ""
                    ),
                    processes=self.processes.value(),
                    local_only=self.local_only.isChecked(),
                    validated=True,
                    version=version,
                    validated_at=datetime.now().isoformat(timespec="seconds"),
                )
                save_lammps_configuration(configuration)
                self.validated_configuration = configuration
                self.configurationChanged.emit(configuration)
                self._set_status(lammps_status_text(configuration), "complete")
                self.log.appendPlainText("\nSmoke test passed. Configuration saved.")
            else:
                reason = "timed out" if self._timed_out else f"exited with code {exit_code}"
                self._set_status(f"Smoke test failed: {reason}. Review the output below.", "failed")
        finally:
            self.timeout.stop()
            self._set_testing(False)
            self._cleanup_smoke_directory()

    def _process_error(self, error):
        if not self._test_active or error != QtCore.QProcess.ProcessError.FailedToStart:
            return
        message = f"Failed to start: {self.process.errorString()}"
        self._captured_output += f"\n{message}\n"
        self.log.appendPlainText(message)
        self.timeout.stop()
        self._set_testing(False)
        self._cleanup_smoke_directory()
        self._set_status(f"Could not start the command: {self.process.errorString()}", "failed")

    def _test_timed_out(self):
        if not self._test_active:
            return
        self._timed_out = True
        self.log.appendPlainText("\nSmoke test exceeded 30 seconds; terminating it…")
        self.process.kill()

    def _set_testing(self, testing: bool):
        self._test_active = testing
        for widget in (
            self.lammps_path,
            self.lammps_browse,
            self.use_mpi,
            self.mpi_path,
            self.mpi_browse,
            self.processes,
            self.local_only,
            self.detect_button,
            self.test_button,
        ):
            widget.setEnabled(not testing)
        if not testing:
            self._mpi_toggled(self.use_mpi.isChecked())
        self.close_button.setText("Cancel test" if testing else "Close")

    def _set_status(self, text: str, state: str):
        self.status.setText(text)
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _cleanup_smoke_directory(self):
        directory = self._smoke_directory
        self._smoke_directory = None
        if directory is not None:
            shutil.rmtree(directory, ignore_errors=True)

    def reject(self):
        if self._test_active:
            self._test_active = False
            self.timeout.stop()
            self.process.kill()
            self.process.waitForFinished(2000)
            self._cleanup_smoke_directory()
        super().reject()

    def closeEvent(self, event):
        if self._test_active:
            self.reject()
            event.accept()
            return
        super().closeEvent(event)
