from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from ..chemistry import (
    build_structure,
    build_system,
    clear_structure_artifacts,
    validate_system_definition,
)
from ..models import MoleculeSpec, ScymolProject, system_definition_signature
from ..project_io import PROJECT_FILENAME, load_project, save_project
from ..protocol import default_protocol, tutorial_protocol
from ..run_generation import generate_run, next_simulation_sequence
from .molecule_drawer.settings import SETTINGS
from .lammps_setup import LammpsSetupDialog, load_lammps_configuration
from .protocol_graph import ProtocolPage
from .process_dialog import ProcessDialog, TaskWorker
from .results_page import ResultsPage
from .runs_page import RunsPage
from .structure_page import StructurePage
from .system_page import SystemPage, SystemSourceDialog
from .tutorial import NewProjectDialog, StartupDialog, TutorialController


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scymol")
        self.resize(1540, 940)
        self.setMinimumSize(1120, 720)
        self.project: ScymolProject | None = None
        self.dirty = False
        self._loading_project = False
        self._task_thread: QtCore.QThread | None = None
        self._task_worker: TaskWorker | None = None
        self._process_dialog: ProcessDialog | None = None
        self._task_page = None
        self._task_on_success: Callable[[Any], None] | None = None
        self._build_actions()
        self._build_ui()
        self._connect_pages()
        self.tutorial = TutorialController(self)
        self.tutorial_action.triggered.connect(self.start_tutorial)
        self._set_project_enabled(False)
        self.update_header()
        QtCore.QTimer.singleShot(0, self._show_first_run)

    def _build_actions(self):
        self.new_action = QtGui.QAction("New project…", self)
        self.open_action = QtGui.QAction("Open project…", self)
        self.save_action = QtGui.QAction("Save", self)
        self.open_folder_action = QtGui.QAction("Open project folder", self)
        self.quit_action = QtGui.QAction("Quit", self)
        self.tutorial_action = QtGui.QAction("Guided tutorial…", self)
        self.lammps_setup_action = QtGui.QAction("LAMMPS execution setup…", self)
        self.new_action.setShortcut(QtGui.QKeySequence.StandardKey.New)
        self.open_action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.save_action.setShortcut(QtGui.QKeySequence.StandardKey.Save)
        self.new_action.triggered.connect(self.show_entry_menu)
        self.open_action.triggered.connect(self.open_project)
        self.save_action.triggered.connect(self.save)
        self.open_folder_action.triggered.connect(self.open_project_folder)
        self.quit_action.triggered.connect(self.close)
        self.lammps_setup_action.triggered.connect(self.configure_lammps_execution)
        menu = self.menuBar().addMenu("File")
        menu.addActions([self.new_action, self.open_action, self.save_action])
        menu.addSeparator()
        menu.addAction(self.open_folder_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        tools_menu = self.menuBar().addMenu("Tools")
        tools_menu.addAction(self.lammps_setup_action)
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(self.tutorial_action)

    def _show_first_run(self):
        if not bool(SETTINGS.get("show_tutorial_on_startup", True)):
            if not load_lammps_configuration().available:
                self.configure_lammps_execution()
            return
        self.show_entry_menu(prompt_lammps_after=True)

    def show_entry_menu(self, prompt_lammps_after: bool = False):
        accepted = False
        choice = ""
        lammps_prompt_shown = False
        while True:
            dialog = StartupDialog(self)
            if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                break
            if dialog.choice == "configure_lammps":
                self.configure_lammps_execution()
                lammps_prompt_shown = True
                continue
            accepted = True
            choice = dialog.choice
            break
        if not accepted:
            if (
                prompt_lammps_after
                and not lammps_prompt_shown
                and not load_lammps_configuration().available
            ):
                self.configure_lammps_execution()
            return
        if choice == "tutorial":
            self.start_tutorial()
        elif choice == "new":
            self.new_project()
        elif choice == "open":
            self.open_project()
        if (
            prompt_lammps_after
            and not lammps_prompt_shown
            and not load_lammps_configuration().available
        ):
            self.configure_lammps_execution()

    def configure_lammps_execution(self, _checked=False):
        dialog = LammpsSetupDialog(self)
        dialog.exec()
        if hasattr(self, "runs_page"):
            self.runs_page.refresh_execution_configuration()

    def start_tutorial(self):
        if not self.maybe_save():
            return
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Choose a folder for the benzene tutorial project",
        )
        if not directory:
            return
        path = Path(directory).resolve() / PROJECT_FILENAME
        if path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Choose another folder",
                "That folder already contains a Scymol project. The tutorial never "
                "overwrites an existing project; choose or create an empty folder.",
            )
            return
        self.project = ScymolProject(
            name="50 benzene molecules · tutorial",
            project_file=str(path),
            molecules=[
                MoleculeSpec(
                    name="benzene",
                    smiles="c1ccccc1",
                    count=50,
                    formula="C6H6",
                    bond_order_status="drawn",
                )
            ],
            system_target_density_kg_m3=876.0,
            system_initial_density_fraction=0.30,
            system_rotate_molecules=True,
            random_seed=29815,
            system_entry_mode="build",
            protocol=tutorial_protocol(),
        )
        self.dirty = True
        self._set_project_enabled(True)
        self.load_into_pages()
        self.system_page.set_status(
            "Needs validation",
            "pending",
            "Review the prepared 50-benzene composition, then validate it.",
        )
        if not self.save():
            return
        self.tabs.setCurrentWidget(self.system_page)
        self.tutorial.start()

    def _build_ui(self):
        central = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = QtWidgets.QFrame()
        header.setObjectName("header")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(18, 10, 18, 10)
        brand = QtWidgets.QLabel("Scymol")
        brand.setObjectName("brand")
        self.project_label = QtWidgets.QLabel()
        self.project_label.setObjectName("projectPath")
        new_button = QtWidgets.QPushButton("New project")
        open_button = QtWidgets.QPushButton("Open")
        self.save_button = QtWidgets.QPushButton("Save")
        new_button.clicked.connect(self.show_entry_menu)
        open_button.clicked.connect(self.open_project)
        self.save_button.clicked.connect(self.save)
        header_layout.addWidget(brand)
        header_layout.addSpacing(20)
        header_layout.addWidget(self.project_label, 1)
        self.project_state = QtWidgets.QLabel("Unsaved")
        self.project_state.setObjectName("stageStatus")
        self.project_state.setProperty("state", "pending")
        header_layout.addWidget(self.project_state)
        header_layout.addWidget(new_button)
        header_layout.addWidget(open_button)
        header_layout.addWidget(self.save_button)
        root.addWidget(header)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.system_page = SystemPage()
        self.structure_page = StructurePage()
        self.protocol_page = ProtocolPage()
        self.runs_page = RunsPage()
        self.results_page = ResultsPage()
        tab_pages = [
            ("1  System", self.system_page),
            ("2  Structure", self.structure_page),
            ("3  Protocol", self.protocol_page),
            ("4  Run", self.runs_page),
            ("5  Results", self.results_page),
        ]
        self._tab_titles: dict[QtWidgets.QWidget, str] = {}
        for title, page in tab_pages:
            self.tabs.addTab(page, title)
            self._tab_titles[page] = title
        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

    def _connect_pages(self):
        for page in [self.system_page, self.structure_page, self.protocol_page]:
            page.changed.connect(self.mark_dirty)
        self.system_page.sourceModeRequested.connect(self._choose_system_source)
        self.system_page.runRequested.connect(self.run_system_build)
        self.structure_page.runRequested.connect(self.run_structure_build)
        self.protocol_page.runRequested.connect(self.protocol_page.validate_and_preview)
        self.runs_page.runRequested.connect(self.run_simulation_generation)
        self.runs_page.recordsChanged.connect(self._run_records_changed)
        self.runs_page.resultsRequested.connect(self._show_run_results)
        self.runs_page.configureLammpsRequested.connect(
            self.configure_lammps_execution
        )
        for page in self._tab_titles:
            page.statusChanged.connect(
                lambda text, state, output, page=page: self._update_tab_status(
                    page, text, state, output
                )
            )
            self._update_tab_status(
                page,
                page.status.text(),
                str(page.status.property("state") or "pending"),
                page.output.text(),
            )
        self.system_page.configure_continue("Continue to Structure")
        self.structure_page.configure_continue("Continue to Protocol")
        self.protocol_page.configure_continue("Continue to Run")
        self.system_page.continueRequested.connect(
            lambda: self.tabs.setCurrentWidget(self.structure_page)
        )
        self.structure_page.continueRequested.connect(
            lambda: self.tabs.setCurrentWidget(self.protocol_page)
        )
        self.protocol_page.continueRequested.connect(
            lambda: self.tabs.setCurrentWidget(self.runs_page)
        )
        self.tabs.currentChanged.connect(self._tab_changed)

    def _update_tab_status(self, page, text: str, state: str, output: str = ""):
        index = self.tabs.indexOf(page)
        if index < 0:
            return
        marker = {
            "complete": "✓",
            "running": "◌",
            "failed": "!",
        }.get(state, "○")
        if state == "pending" and any(
            word in text.lower() for word in ("need", "stale", "rebuild", "changed")
        ):
            marker = "↻"
        self.tabs.setTabText(index, f"{marker}  {self._tab_titles[page]}")
        tooltip = text if not output else f"{text}\n{output}"
        self.tabs.setTabToolTip(index, tooltip)
        color = {
            "complete": QtGui.QColor("#3b7f86"),
            "running": QtGui.QColor("#4b8a92"),
            "failed": QtGui.QColor("#b34b4b"),
        }.get(state, QtGui.QColor("#6f7b80"))
        self.tabs.tabBar().setTabTextColor(index, color)

    def load_into_pages(self):
        if self.project is None:
            return
        intended_dirty = self.dirty
        self._loading_project = True
        try:
            self.system_page.load_project(self.project)
            self.structure_page.load_project(self.project)
            self.protocol_page.load_graph(self.project.protocol)
            self.runs_page.load_project(self.project)
            self.results_page.load_project(self.project)
        finally:
            self._loading_project = False
            self.dirty = intended_dirty
            self.update_header()

    def commit_pages(self):
        if self.project is None:
            return
        self.system_page.commit()
        self.structure_page.commit()
        self.project.protocol = self.protocol_page.editor.graph

    def mark_dirty(self, *_):
        if self._loading_project or self.project is None:
            return
        self.dirty = True
        self.update_header()

    def update_header(self):
        if self.project is None:
            self.project_label.setText("No project open — create or open a project to begin")
            self.project_label.setToolTip("")
            self.project_state.setText("No project")
            self.project_state.setProperty("state", "pending")
            self.project_state.style().unpolish(self.project_state)
            self.project_state.style().polish(self.project_state)
            self.setWindowTitle("Scymol")
            return
        location = str(self.project.root)
        self.project_label.setText(self.project.name)
        self.project_label.setToolTip(location)
        self.project_state.setText("Unsaved changes" if self.dirty else "Saved")
        self.project_state.setProperty("state", "running" if self.dirty else "complete")
        self.project_state.style().unpolish(self.project_state)
        self.project_state.style().polish(self.project_state)
        suffix = " *" if self.dirty else ""
        self.setWindowTitle(f"{self.project.name}{suffix} — Scymol")

    def maybe_save(self) -> bool:
        if self.project is None or not self.dirty:
            return True
        answer = QtWidgets.QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes to the current Scymol project?",
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Cancel:
            return False
        if answer == QtWidgets.QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def new_project(self):
        if not self.maybe_save():
            return
        dialog = NewProjectDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        directory = dialog.project_directory
        if directory is None:
            return
        path = directory / PROJECT_FILENAME
        self.project = ScymolProject(
            name=dialog.project_name,
            project_file=str(path),
            system_entry_mode=dialog.source_mode,
            protocol=default_protocol(),
        )
        if dialog.source_mode in {"import", "merge"}:
            self.project.molecules = []
        self.dirty = True
        self._set_project_enabled(True)
        self.load_into_pages()
        self.save()
        self._prepare_system_source()

    def open_project(self):
        if not self.maybe_save():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Scymol project",
            "",
            "Scymol project (scymol.json *.scymol.json);;JSON files (*.json)",
        )
        if not path:
            return
        self._load_project_path(Path(path))

    def _load_project_path(self, path: Path):
        try:
            self.project = load_project(path)
        except Exception as exc:
            self.show_error("Cannot open project", exc)
            return
        self.dirty = False
        self._set_project_enabled(True)
        self.load_into_pages()
        self.statusBar().showMessage(f"Opened {path}", 5000)
        self._prepare_system_source()

    def _prepare_system_source(self):
        if self.project is None or self.system_page.has_system_result():
            return
        self.tabs.setCurrentWidget(self.system_page)
        if self.project.system_entry_mode == "import":
            self.system_page.structure_file.setFocus()
        elif self.project.system_entry_mode == "merge":
            self.system_page.merge_add_button.setFocus()
        else:
            self.system_page.canvas.setFocus()

    @QtCore.Slot(str)
    def _choose_system_source(self, requested_mode: str = ""):
        if self.project is None:
            return
        has_result = self.system_page.has_system_result()
        current_mode = self.project.system_entry_mode
        mode = requested_mode
        if not mode:
            dialog = SystemSourceDialog(current_mode if has_result else "", self)
            if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                if not has_result:
                    self.system_page.set_source_unconfigured()
                return
            mode = dialog.selected_mode
        if mode not in {"build", "import", "merge"}:
            return
        if has_result and mode != current_mode:
            answer = QtWidgets.QMessageBox.warning(
                self,
                "Change the system input method?",
                "The current molecular definition remains untouched until you validate or analyze "
                "the new method. Doing so will make the existing Stage 2 structure stale.\n\nContinue?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        self.tabs.setCurrentWidget(self.system_page)
        self.system_page.set_source_mode(mode)
        self.mark_dirty()
        self.save()
        if mode == "import":
            self.system_page.structure_file.setFocus()
        elif mode == "merge":
            self.system_page.merge_add_button.setFocus()
        else:
            self.system_page.canvas.setFocus()

    def save(self) -> bool:
        if self.project is None:
            return False
        try:
            self.commit_pages()
            path = save_project(self.project)
        except Exception as exc:
            self.show_error("Cannot save project", exc)
            return False
        self.dirty = False
        self.update_header()
        self.statusBar().showMessage(f"Saved {path}", 5000)
        return True

    def run_system_build(self):
        if self.project is None:
            return
        if self.project.system_entry_mode == "merge":
            try:
                self.system_page.validate_merge_inputs()
            except Exception as exc:
                self.system_page.set_status("Needs attention", "failed", str(exc))
                self.show_error("Cannot merge systems", exc)
                return
            warning = QtWidgets.QMessageBox(self)
            warning.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            warning.setWindowTitle("Review merged-system placement")
            warning.setText(
                "Scymol will preserve the selected coordinates and translations as entered."
            )
            warning.setInformativeText(
                "It will not remove overlaps, repair periodic interfaces, or determine whether "
                "the resulting contact geometry is physically suitable. Inspect the merged "
                "structure before running LAMMPS."
            )
            continue_button = warning.addButton(
                "Continue", QtWidgets.QMessageBox.ButtonRole.AcceptRole
            )
            warning.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            warning.exec()
            if warning.clickedButton() is not continue_button:
                return
        self.commit_pages()
        project = self.project
        if project.system_entry_mode == "build":
            try:
                result = validate_system_definition(project)
            except Exception as exc:
                self.system_page.set_status("Needs attention", "failed", str(exc))
                self.show_error("Cannot validate molecular system", exc)
                return
            project.system_definition_signature = result["signature"]
            self.system_page.set_status(
                "Validated",
                "complete",
                f"{result['species_count']} species · {result['molecule_count']} molecules · ready for 3-D structure preparation",
            )
            self.structure_page.refresh_files()
            self.mark_dirty()
            self.save()
            return

        if (
            project.system_entry_mode == "import"
            and not project.imported_structure_file
            and project.imported_trajectory_file
        ):
            answer = QtWidgets.QMessageBox.warning(
                self,
                "Infer topology from trajectory?",
                "Scymol will use the last trajectory frame as the starting structure and infer "
                "molecule boundaries and bonds from it. "
                "Dense or wrapped systems can produce incorrect connectivity, so review the detected "
                "SMILES before continuing. You may then reuse that snapshot directly or parameterize "
                "it again in Stage 2.\n\nContinue?",
                QtWidgets.QMessageBox.StandardButton.Ok
                | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Ok:
                return

        def completed(result: dict):
            clear_structure_artifacts(project)
            project.system_definition_signature = system_definition_signature(project)
            self.system_page.refresh_detected()
            project.system_definition_signature = system_definition_signature(project)
            detail = f"Identified {result['molecule_count']} molecules · {result['system_pdb']}"
            if result.get("warnings"):
                detail += f" · Warning: {result['warnings'][0]}"
            self.system_page.set_status(
                "Complete", "complete", detail
            )
            self.structure_page.refresh_files()
            self.results_page.refresh()
            self.mark_dirty()
            self.save()

        self._start_background_task(
            "Analyze and merge systems"
            if project.system_entry_mode == "merge"
            else "Analyze existing system",
            self.system_page,
            lambda progress: build_system(project, progress=progress),
            completed,
        )

    def run_structure_build(self):
        if self.project is None:
            return
        self.commit_pages()
        project = self.project

        expected_definition = system_definition_signature(project)
        if project.system_definition_signature != expected_definition:
            self.system_page.set_status(
                "Needs validation",
                "failed",
                "Validate the current molecular definition before building its structure.",
            )
            self.tabs.setCurrentWidget(self.system_page)
            return

        def prepare(progress):
            system_result = None
            if project.system_entry_mode == "build":
                progress("Generating the validated molecular system geometry.")
                system_result = build_system(project, progress=progress)
            elif project.structure.source_mode == "rebuild":
                progress("Rebuilding geometry from the detected molecular composition.")
                system_result = build_system(
                    project, progress=progress, rebuild_imported=True
                )
            structure_result = build_structure(
                project,
                progress=progress,
                geometry_manifest=(
                    system_result["manifest"]
                    if project.structure.source_mode == "rebuild" and system_result
                    else None
                ),
            )
            return {"system": system_result, "structure": structure_result}

        def completed(payload: dict):
            result = payload["structure"]
            detail = result["structure_data"]
            system_result = payload.get("system")
            if system_result and system_result.get("packing"):
                packing = system_result["packing"]
                actual_percent = 100.0 * packing["actual_initial_density_fraction"]
                detail += (
                    f" · Sobol-packed at {actual_percent:.3g}% target density"
                    f" · {packing['rejected_candidates']} clashes rejected"
                )
            self.structure_page.set_status("Complete", "complete", detail)
            self.structure_page.refresh_files()
            self.results_page.refresh()
            self.mark_dirty()
            self.save()

        task_title = (
            "Preserve imported configuration and parameters"
            if project.structure.source_mode == "imported"
            else "Reparameterize merged geometry"
            if project.system_entry_mode == "merge"
            else "Reparameterize without moving imported atoms"
            if project.structure.source_mode == "parameterize"
            else "Rebuild mixture from detected molecules"
            if project.structure.source_mode == "rebuild"
            else "Build 3-D and LAMMPS structure"
            if project.system_entry_mode == "build"
            else "Prepare LAMMPS structure"
        )
        self._start_background_task(
            task_title,
            self.structure_page,
            prepare,
            completed,
        )

    def run_simulation_generation(self):
        if self.project is None:
            return
        self.commit_pages()
        if not self.protocol_page.validate_and_preview():
            self.tabs.setCurrentWidget(self.protocol_page)
            return
        project = self.project
        destination = project.output_root / "simulations"
        sequence = next_simulation_sequence(project)
        simulation_name = self.runs_page.requested_simulation_name()

        def completed(record):
            project.runs.append(record)
            self.runs_page.set_records(project.runs)
            self.runs_page.preparation_succeeded()
            self.results_page.refresh()
            self.mark_dirty()
            self.save()

        self._start_background_task(
            "Prepare simulation",
            self.runs_page,
            lambda progress: generate_run(
                project,
                destination,
                sequence,
                simulation_name,
                progress=progress,
            ),
            completed,
        )

    def _start_background_task(
        self,
        title: str,
        page,
        task: Callable[[Callable[[str], None]], Any],
        on_success: Callable[[Any], None],
    ):
        if self._task_thread is not None and self._task_thread.isRunning():
            if self._process_dialog is not None:
                self._process_dialog.show()
                self._process_dialog.raise_()
                self._process_dialog.activateWindow()
            return
        if self.project is None:
            return

        page.set_running(True)
        dialog = ProcessDialog(title, self.project.name, str(self.project.root), self)
        worker = TaskWorker(task)
        thread = QtCore.QThread(self)
        worker.moveToThread(thread)

        self._process_dialog = dialog
        self._task_worker = worker
        self._task_thread = thread
        self._task_page = page
        self._task_on_success = on_success

        dialog.destroyed.connect(self._process_dialog_destroyed)
        worker.logReceived.connect(dialog.append_log)
        worker.succeeded.connect(self._background_task_succeeded)
        worker.failed.connect(self._background_task_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_background_task)
        thread.started.connect(worker.run)

        dialog.append_log(f"Started: {title}")
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        thread.start()

    @QtCore.Slot(object)
    def _background_task_succeeded(self, result):
        page = self._task_page
        on_success = self._task_on_success
        dialog = self._process_dialog
        if page is None or on_success is None or dialog is None:
            return
        try:
            on_success(result)
        except Exception as exc:
            import traceback

            self._background_task_failed(str(exc), traceback.format_exc())
            return
        page.set_running(False)
        dialog.append_log("Completed successfully.")
        dialog.finish_run(True)
        self.statusBar().showMessage(f"{dialog.windowTitle()}", 8000)

    @QtCore.Slot(str, str)
    def _background_task_failed(self, message: str, detail: str):
        page = self._task_page
        dialog = self._process_dialog
        if page is None or dialog is None:
            return
        page.set_status("Failed", "failed", message)
        page.set_running(False)
        dialog.append_log(f"ERROR: {message}")
        dialog.append_traceback(detail)
        dialog.finish_run(False)
        self.statusBar().showMessage(message, 8000)

    @QtCore.Slot()
    def _clear_background_task(self):
        self._task_thread = None
        self._task_worker = None
        self._task_page = None
        self._task_on_success = None

    @QtCore.Slot()
    def _process_dialog_destroyed(self):
        self._process_dialog = None

    def open_project_folder(self):
        if self.project is None:
            return
        self.project.root.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.project.root)))

    def _run_records_changed(self):
        if self.project is None:
            return
        self.project.runs = self.runs_page.records
        self.mark_dirty()
        if self.project.project_file:
            self.save()

    def _show_run_results(self, output_dir: str):
        self.results_page.refresh()
        self.tabs.setCurrentWidget(self.results_page)
        self.results_page.show_path(output_dir)

    def _tab_changed(self, index: int):
        if self.project is None:
            return
        if self.tabs.widget(index) is self.results_page:
            self.results_page.refresh()

    def show_error(self, title: str, exc: Exception):
        QtWidgets.QMessageBox.critical(self, title, str(exc))
        self.statusBar().showMessage(str(exc), 8000)

    def _set_project_enabled(self, enabled: bool):
        self.tabs.setEnabled(enabled)
        self.save_action.setEnabled(enabled)
        self.open_folder_action.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.statusBar().showMessage(
            "Ready" if enabled else "Create or open a project to begin"
        )

    def closeEvent(self, event):
        if self._task_thread is not None and self._task_thread.isRunning():
            if self._process_dialog is not None:
                self._process_dialog.show()
                self._process_dialog.raise_()
                self._process_dialog.activateWindow()
            event.ignore()
            return
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()
