from __future__ import annotations

import json
from pathlib import Path
import sys

from PySide6 import QtCore, QtGui, QtWidgets

from ..models import ScymolProject
from .base import StagePage


class _ResultWorkerSignals(QtCore.QObject):
    result = QtCore.Signal(object)
    error = QtCore.Signal(str)
    finished = QtCore.Signal()


class _ResultWorker(QtCore.QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = _ResultWorkerSignals()

    @QtCore.Slot()
    def run(self):
        try:
            self.signals.result.emit(self.operation())
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class ResultsPage(StagePage):
    PATH_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) + 1
    KIND_ROLE = PATH_ROLE + 1

    def __init__(self, parent=None):
        super().__init__(
            "5 · Results",
            "Browse generated files in text, interactive 3-D, or numeric plot/analysis views.",
            None,
            parent,
        )
        self.compact_header()
        self.use_workspace_layout()
        self.root = Path.cwd()
        self._preview_generation = 0
        self._workers = set()
        self._selected_path: Path | None = None
        self._trajectory = None
        self._requested_frame = -1
        self._frame_loading = False

        actions = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.open_button = QtWidgets.QPushButton("Open output root")
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.open_button)
        self.selection_summary = QtWidgets.QLabel("No artifact selected")
        self.selection_summary.setObjectName("note")
        self.selection_summary.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        actions.addWidget(self.selection_summary, 1)
        self.text_view_button = QtWidgets.QPushButton("Text")
        self.molecular_view_button = QtWidgets.QPushButton("3-D")
        self.plot_view_button = QtWidgets.QPushButton("Plot")
        self.view_mode_group = QtWidgets.QButtonGroup(self)
        self.view_mode_group.setExclusive(True)
        for button in (
            self.text_view_button,
            self.molecular_view_button,
            self.plot_view_button,
        ):
            button.setCheckable(True)
            button.setObjectName("viewModeButton")
            button.setEnabled(False)
            self.view_mode_group.addButton(button)
        actions.addWidget(self.text_view_button)
        actions.addWidget(self.molecular_view_button)
        actions.addWidget(self.plot_view_button)
        self.maximize_button = QtWidgets.QPushButton("Maximize preview")
        self.maximize_button.setCheckable(True)
        actions.addWidget(self.maximize_button)
        self.layout.addLayout(actions)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.tree_panel = QtWidgets.QWidget()
        tree_layout = QtWidgets.QVBoxLayout(self.tree_panel)
        tree_layout.setContentsMargins(0, 0, 4, 0)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Filter results by name…")
        tree_layout.addWidget(self.search)
        self.show_all_files = QtWidgets.QCheckBox("Show all files")
        self.show_all_files.setToolTip(
            "Include auxiliary files that are normally hidden from prepared simulations."
        )
        tree_layout.addWidget(self.show_all_files)
        self.model = QtGui.QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels(["Results"])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setRecursiveFilteringEnabled(True)
        self.tree = QtWidgets.QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(False)
        self.tree.setHeaderHidden(False)
        tree_layout.addWidget(self.tree, 1)
        self.splitter.addWidget(self.tree_panel)

        self.preview_stack = QtWidgets.QStackedWidget()
        self.text_page = QtWidgets.QWidget()
        text_layout = QtWidgets.QVBoxLayout(self.text_page)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = QtWidgets.QPlainTextEdit()
        self.preview.setObjectName("scriptPreview")
        self.preview.setReadOnly(True)
        text_layout.addWidget(self.preview, 1)
        self.preview_stack.addWidget(self.text_page)

        self.molecular_page = QtWidgets.QWidget()
        molecular_layout = QtWidgets.QVBoxLayout(self.molecular_page)
        molecular_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QtWidgets.QHBoxLayout()
        self.molecular_summary = QtWidgets.QLabel("No molecular file selected")
        self.molecular_summary.setObjectName("note")
        self.molecular_summary.setWordWrap(True)
        self.pbc_checkbox = QtWidgets.QCheckBox("Whole molecules")
        self.pbc_checkbox.setToolTip("Make bonded molecules whole across periodic boundaries")
        self.pbc_checkbox.setChecked(True)
        self.reset_button = QtWidgets.QPushButton("Reset")
        self.reset_button.setToolTip("Reset to the fitted isometric camera")
        self.view_button = QtWidgets.QPushButton("View")
        view_menu = QtWidgets.QMenu(self.view_button)
        for label, camera_view in (
            ("Isometric", "isometric"),
            ("Front", "front"),
            ("Side", "side"),
            ("Top", "top"),
        ):
            action = view_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, name=camera_view: self._set_camera_view(name)
            )
        self.view_button.setMenu(view_menu)
        self.display_button = QtWidgets.QPushButton("Display")
        display_menu = QtWidgets.QMenu(self.display_button)
        self.atoms_action = display_menu.addAction("Atoms")
        self.bonds_action = display_menu.addAction("Bonds")
        self.box_action = display_menu.addAction("Simulation box")
        for action in (self.atoms_action, self.bonds_action, self.box_action):
            action.setCheckable(True)
            action.setChecked(True)
        self.display_button.setMenu(display_menu)
        self.export_view_button = QtWidgets.QPushButton("PNG…")
        self.export_view_button.setToolTip("Save the current antialiased 3D view as a PNG image")
        molecular_layout.addWidget(self.molecular_summary)
        toolbar.addStretch(1)
        toolbar.addWidget(self.pbc_checkbox)
        toolbar.addWidget(self.reset_button)
        toolbar.addWidget(self.view_button)
        toolbar.addWidget(self.display_button)
        toolbar.addWidget(self.export_view_button)
        molecular_layout.addLayout(toolbar)

        self.viewer = None
        self.viewer_error = ""
        try:
            from .molecular_viewer_3d import MolecularViewerWidget, empty_scene

            self.viewer = MolecularViewerWidget(
                self.molecular_page, scene=empty_scene(), embedded=True
            )
            molecular_layout.addWidget(self.viewer, 1)
        except (ImportError, RuntimeError) as exc:
            self.viewer_error = str(exc)
            unavailable = QtWidgets.QLabel(
                "3-D preview is unavailable. Install NumPy and ModernGL, then restart Scymol.\n\n"
                + self.viewer_error
            )
            unavailable.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            unavailable.setWordWrap(True)
            molecular_layout.addWidget(unavailable, 1)

        trajectory_row = QtWidgets.QHBoxLayout()
        self.previous_frame_button = QtWidgets.QPushButton("◀")
        self.previous_frame_button.setToolTip("Previous trajectory frame")
        self.previous_frame_button.setFixedWidth(34)
        self.play_button = QtWidgets.QPushButton("Play")
        self.play_button.setCheckable(True)
        self.play_button.setFixedWidth(58)
        self.next_frame_button = QtWidgets.QPushButton("▶")
        self.next_frame_button.setToolTip("Next trajectory frame")
        self.next_frame_button.setFixedWidth(34)
        self.playback_speed = QtWidgets.QComboBox()
        for label, speed in (("0.25×", 0.25), ("0.5×", 0.5), ("1×", 1.0), ("2×", 2.0), ("4×", 4.0)):
            self.playback_speed.addItem(label, speed)
        self.playback_speed.setCurrentText("1×")
        self.frame_label = QtWidgets.QLabel("Frame — / —")
        self.frame_label.setFixedWidth(260)
        self.frame_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setEnabled(False)
        trajectory_row.addWidget(self.previous_frame_button)
        trajectory_row.addWidget(self.play_button)
        trajectory_row.addWidget(self.next_frame_button)
        trajectory_row.addWidget(self.playback_speed)
        trajectory_row.addWidget(self.frame_label)
        trajectory_row.addWidget(self.frame_slider, 1)
        molecular_layout.addLayout(trajectory_row)
        hint = QtWidgets.QLabel(
            "Left drag: orbit · Right/middle drag: pan · Wheel: zoom · F: reset"
        )
        hint.setObjectName("note")
        molecular_layout.addWidget(hint)

        self.preview_stack.addWidget(self.molecular_page)
        self.data_plot = None
        self.data_plot_error = ""
        try:
            from .data_plot import DataPlotWidget

            self.data_plot = DataPlotWidget(self.preview_stack)
            self.preview_stack.addWidget(self.data_plot)
        except (ImportError, RuntimeError) as exc:
            self.data_plot_error = str(exc)

        self.numeric_error_page = QtWidgets.QWidget()
        numeric_error_layout = QtWidgets.QVBoxLayout(self.numeric_error_page)
        numeric_error_layout.addStretch()
        self.numeric_error_title = QtWidgets.QLabel("Numeric plot unavailable")
        self.numeric_error_title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.numeric_error_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.numeric_error_detail = QtWidgets.QLabel()
        self.numeric_error_detail.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.numeric_error_detail.setWordWrap(True)
        self.numeric_error_detail.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        numeric_error_layout.addWidget(self.numeric_error_title)
        numeric_error_layout.addWidget(self.numeric_error_detail)
        numeric_error_layout.addStretch()
        self.preview_stack.addWidget(self.numeric_error_page)
        self.splitter.addWidget(self.preview_stack)
        self.splitter.setSizes([430, 780])
        self.layout.addWidget(self.splitter, 1)

        self.tree.selectionModel().currentChanged.connect(self.preview_file)
        self.tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_result_context_menu)
        self.refresh_button.clicked.connect(self.refresh)
        self.open_button.clicked.connect(self.open_root)
        self.text_view_button.clicked.connect(self._request_text_view)
        self.molecular_view_button.clicked.connect(self._request_molecular_view)
        self.plot_view_button.clicked.connect(self._request_plot_view)
        self.maximize_button.toggled.connect(self._toggle_maximized)
        self.search.textChanged.connect(self.proxy.setFilterFixedString)
        self.show_all_files.toggled.connect(self.refresh)
        self.pbc_checkbox.toggled.connect(self._set_pbc)
        self.reset_button.clicked.connect(self._reset_camera)
        self.export_view_button.clicked.connect(self._export_current_view)
        self.atoms_action.toggled.connect(self._set_atoms_visible)
        self.bonds_action.toggled.connect(self._set_bonds_visible)
        self.box_action.toggled.connect(self._set_box_visible)
        self.frame_slider.valueChanged.connect(self._queue_frame)
        self.previous_frame_button.clicked.connect(lambda: self._step_frame(-1))
        self.next_frame_button.clicked.connect(lambda: self._step_frame(1))
        self.play_button.toggled.connect(self._toggle_playback)
        self.playback_speed.currentIndexChanged.connect(self._update_playback_speed)
        self.playback_timer = QtCore.QTimer(self)
        self.playback_timer.timeout.connect(self._advance_playback)
        self._update_playback_speed()
        self.pbc_checkbox.setEnabled(False)
        self._set_molecular_controls_enabled(False)
        self._set_playback_controls_enabled(False)

    def load_project(self, project: ScymolProject):
        self.root = project.output_root
        self.refresh()

    def refresh(self):
        self.root.mkdir(parents=True, exist_ok=True)
        selected = self._selected_path
        self.model.removeRows(0, self.model.rowCount())
        artifact_count = self._populate_directory(self.model.invisibleRootItem(), self.root)
        self.tree.expandToDepth(0)
        self.tree.setColumnWidth(0, 390)
        if selected:
            self.show_path(selected)
        self.set_status(
            "Ready" if artifact_count else "Pending",
            "complete" if artifact_count else "pending",
            f"{artifact_count} artifact(s) · {self.root}" if artifact_count else "No generated files yet",
        )

    def _populate_directory(self, parent, directory: Path):
        if self._is_simulation_directory(directory):
            return self._populate_simulation(parent, directory)
        try:
            entries = sorted(directory.iterdir(), key=lambda path: (path.is_file(), path.name.lower()))
        except OSError:
            return 0
        count = 0
        for child in (path for path in entries if path.is_dir()):
            item = QtGui.QStandardItem(child.name)
            item.setEditable(False)
            item.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon))
            item.setData(str(child), self.PATH_ROLE)
            item.setData("folder", self.KIND_ROLE)
            parent.appendRow(item)
            count += self._populate_directory(item, child)
        for child in (path for path in entries if path.is_file()):
            self._append_file(parent, child)
            count += 1
        return count

    @staticmethod
    def _is_simulation_directory(directory: Path) -> bool:
        return (directory / "run_manifest.json").is_file() and (
            directory / "stages"
        ).is_dir()

    def _populate_simulation(self, parent, directory: Path) -> int:
        count = 0
        stages_directory = directory / "stages"
        stages_group = QtGui.QStandardItem("Stages")
        stages_group.setEditable(False)
        stages_group.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
        )
        stages_group.setData(str(stages_directory), self.PATH_ROLE)
        stages_group.setData("stage_group", self.KIND_ROLE)
        parent.appendRow(stages_group)
        try:
            stage_directories = sorted(
                (path for path in stages_directory.iterdir() if path.is_dir()),
                key=lambda path: path.name.lower(),
            )
        except OSError:
            stage_directories = []
        for stage_directory in stage_directories:
            stage_item = QtGui.QStandardItem(self._stage_display_name(stage_directory.name))
            stage_item.setEditable(False)
            stage_item.setIcon(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
            )
            stage_item.setData(str(stage_directory), self.PATH_ROLE)
            stage_item.setData("stage", self.KIND_ROLE)
            stages_group.appendRow(stage_item)
            try:
                iteration_directories = sorted(
                    (path for path in stage_directory.iterdir() if path.is_dir()),
                    key=lambda path: path.name.lower(),
                )
                files = sorted(
                    (path for path in stage_directory.iterdir() if path.is_file()),
                    key=lambda path: (self._stage_file_priority(path), path.name.lower()),
                )
            except OSError:
                iteration_directories = []
                files = []
            for iteration_directory in iteration_directories:
                label = iteration_directory.name
                if label.startswith("i_"):
                    label = f"i = {label[2:]}"
                iteration_item = QtGui.QStandardItem(label)
                iteration_item.setEditable(False)
                iteration_item.setIcon(
                    self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
                )
                iteration_item.setData(str(iteration_directory), self.PATH_ROLE)
                iteration_item.setData("iteration", self.KIND_ROLE)
                stage_item.appendRow(iteration_item)
                try:
                    iteration_files = sorted(
                        (path for path in iteration_directory.iterdir() if path.is_file()),
                        key=lambda path: (
                            self._stage_file_priority(path),
                            path.name.lower(),
                        ),
                    )
                except OSError:
                    iteration_files = []
                for path in iteration_files:
                    self._append_file(iteration_item, path)
                    count += 1
            for path in files:
                self._append_file(stage_item, path)
                count += 1

        essentials = [
            path
            for path in directory.iterdir()
            if path.is_file()
            and (
                path.suffix.lower() in {".in", ".json"}
                or path.name.lower() == "structure.data"
            )
        ]
        if essentials:
            setup_group = QtGui.QStandardItem("Simulation files")
            setup_group.setEditable(False)
            setup_group.setData("simulation_files", self.KIND_ROLE)
            parent.appendRow(setup_group)
            for path in sorted(essentials, key=lambda item: item.name.lower()):
                self._append_file(setup_group, path)
                count += 1

        if self.show_all_files.isChecked():
            excluded = {path.resolve() for path in essentials}
            extra_files = [
                path
                for path in directory.iterdir()
                if path.is_file() and path.resolve() not in excluded
            ]
            extra_directories = [
                path
                for path in directory.iterdir()
                if path.is_dir() and path.name != "stages"
            ]
            if extra_files or extra_directories:
                extra_group = QtGui.QStandardItem("Other files")
                extra_group.setEditable(False)
                extra_group.setData("other_files", self.KIND_ROLE)
                parent.appendRow(extra_group)
                for path in sorted(extra_directories, key=lambda item: item.name.lower()):
                    item = QtGui.QStandardItem(path.name)
                    item.setEditable(False)
                    item.setIcon(
                        self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
                    )
                    item.setData(str(path), self.PATH_ROLE)
                    item.setData("folder", self.KIND_ROLE)
                    extra_group.appendRow(item)
                    count += self._populate_directory(item, path)
                for path in sorted(extra_files, key=lambda item: item.name.lower()):
                    self._append_file(extra_group, path)
                    count += 1
        return count

    def _append_file(self, parent, path: Path):
        category = self._artifact_category(path)
        item = QtGui.QStandardItem(path.name)
        item.setEditable(False)
        item.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon))
        item.setData(str(path), self.PATH_ROLE)
        item.setData(category, self.KIND_ROLE)
        item.setToolTip(str(path))
        parent.appendRow(item)

    @staticmethod
    def _stage_display_name(name: str) -> str:
        number, separator, label = name.partition("_")
        words = [
            word.upper() if word.lower() in {"nvt", "npt", "nve"} else word.title()
            for word in label.split("_")
        ]
        if separator and number.isdigit():
            return f"{number}  {' '.join(words)}"
        return name.replace("_", " ").title()

    def _stage_file_priority(self, path: Path) -> int:
        category = self._artifact_category(path)
        return {
            "Trajectories": 0,
            "Numeric results": 1,
            "Structures": 2,
        }.get(category, 3)

    @staticmethod
    def _artifact_category(path: Path) -> str:
        name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix in {".lammpstrj", ".dump", ".traj", ".dcd", ".xtc"}:
            return "Trajectories"
        if suffix in {".pdb", ".gro", ".xyz", ".mol", ".mol2"} or (
            suffix == ".data" and "structure" in name
        ):
            return "Structures"
        if name == "log.lammps" or suffix in {".out", ".csv", ".tsv", ".dat"}:
            return "Numeric results"
        if suffix in {".in", ".sh", ".bat", ".ps1"}:
            return "Scripts"
        if suffix in {".log", ".txt", ".json", ".yaml", ".yml"}:
            return "Logs and metadata"
        return "Other files"

    def preview_file(self, index, *_):
        self._stop_playback()
        source_index = self.proxy.mapToSource(index)
        raw_path = self.model.data(source_index, self.PATH_ROLE)
        path = Path(raw_path) if raw_path else None
        self._preview_generation += 1
        self._selected_path = path if path and path.is_file() else None
        self._trajectory = None
        self._requested_frame = -1
        self._frame_loading = False
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(False)
        self.frame_label.setText("Frame — / —")
        self.pbc_checkbox.setEnabled(False)
        self._set_molecular_controls_enabled(False)
        self._set_playback_controls_enabled(False)
        is_file = bool(path and path.is_file())
        is_numeric = is_file and self._numeric_candidate(path)
        kind = self._molecular_kind(path) if is_file else None
        self.text_view_button.setEnabled(is_file)
        self.molecular_view_button.setEnabled(bool(kind and self.viewer is not None))
        self.plot_view_button.setEnabled(is_numeric)
        artifact_type = kind.title() if kind else self.model.data(source_index, self.KIND_ROLE) or "Folder"
        self.selection_summary.setText(
            f"{path.name}  ·  {artifact_type}" if is_file else "No previewable artifact selected"
        )
        self.selection_summary.setToolTip(str(path) if path else "")
        self.plot_view_button.setToolTip(
            "Open this numeric file in the table and plotting workspace."
            if is_numeric
            else "Select a .out, .dat, .csv, .tsv, or LAMMPS log file."
        )

        if not is_file:
            self.preview.setPlainText(str(path) if path else "Select a file to preview it.")
            self.preview_stack.setCurrentWidget(self.text_page)
            self._set_mode_checked(None)
            return

        if kind and self.viewer is not None:
            self._set_mode_checked(self.molecular_view_button)
            self.preview_stack.setCurrentWidget(self.molecular_page)
            self.molecular_summary.setText(f"Loading {path.name}…")
            self.reset_button.setEnabled(False)
            self.pbc_checkbox.setEnabled(False)
            if kind == "structure":
                self._load_structure(path, self._preview_generation)
            else:
                self._load_trajectory(path, self._preview_generation)
            return

        if is_numeric:
            self._set_mode_checked(self.plot_view_button)
            self._open_numeric_view(path, self._preview_generation)
            return

        self._show_text(path)
        self.preview_stack.setCurrentWidget(self.text_page)
        self._set_mode_checked(self.text_view_button)

    @staticmethod
    def _numeric_candidate(path: Path) -> bool:
        return path.name.lower() == "log.lammps" or path.suffix.lower() in {
            ".out",
            ".csv",
            ".tsv",
            ".dat",
            ".log",
        }

    def _load_numeric_data(self, path: Path, generation: int):
        from ..analysis import parse_numeric_file

        def load():
            return parse_numeric_file(path)

        worker = _ResultWorker(load)
        self._start_worker(
            worker,
            lambda payload: self._numeric_data_loaded(generation, path, payload),
            lambda message: self._numeric_data_failed(generation, path, message),
        )

    def _open_numeric_view(self, path: Path, generation: int):
        if self.data_plot is None:
            executable = str(Path(sys.executable).resolve())
            reason = self.data_plot_error or "Matplotlib could not be imported."
            self._show_numeric_error(
                "Plotting component could not start",
                f"{reason}\n\nInstall Matplotlib into the same Python environment used to run Scymol:\n"
                f'"{executable}" -m pip install matplotlib',
            )
            return
        self.preview_stack.setCurrentWidget(self.data_plot)
        self.data_plot.set_loading(path)
        self._load_numeric_data(path, generation)

    def _show_numeric_error(self, title: str, detail: str):
        self.numeric_error_title.setText(title)
        self.numeric_error_detail.setText(detail)
        self.preview_stack.setCurrentWidget(self.numeric_error_page)

    def _request_text_view(self):
        if self._selected_path is None:
            return
        self._stop_playback()
        self._show_text(self._selected_path)
        self.preview_stack.setCurrentWidget(self.text_page)
        self._set_mode_checked(self.text_view_button)

    def _request_molecular_view(self):
        path = self._selected_path
        if path is None or self.viewer is None:
            return
        kind = self._molecular_kind(path)
        if not kind:
            return
        self._set_mode_checked(self.molecular_view_button)
        self.preview_stack.setCurrentWidget(self.molecular_page)
        if kind == "structure":
            self._load_structure(path, self._preview_generation)
        else:
            self._load_trajectory(path, self._preview_generation)

    def _request_plot_view(self):
        path = self._selected_path
        if path is None or not self._numeric_candidate(path):
            return
        self._stop_playback()
        self._set_mode_checked(self.plot_view_button)
        self._open_numeric_view(path, self._preview_generation)

    def _set_mode_checked(self, active):
        for button in (
            self.text_view_button,
            self.molecular_view_button,
            self.plot_view_button,
        ):
            button.blockSignals(True)
            button.setChecked(button is active)
            button.blockSignals(False)

    def _toggle_maximized(self, maximized: bool):
        self.tree_panel.setVisible(not maximized)
        self.maximize_button.setText("Restore browser" if maximized else "Maximize preview")

    def show_path(self, path: str | Path):
        target = str(Path(path).resolve())

        def visit(parent):
            for row in range(parent.rowCount()):
                item = parent.child(row)
                raw = item.data(self.PATH_ROLE)
                if raw:
                    try:
                        if str(Path(raw).resolve()) == target:
                            return item
                    except OSError:
                        pass
                found = visit(item)
                if found:
                    return found
            return None

        item = visit(self.model.invisibleRootItem())
        if item is None:
            return False
        index = self.proxy.mapFromSource(item.index())
        if not index.isValid():
            return False
        self.tree.setCurrentIndex(index)
        self.tree.expand(index)
        if item.data(self.KIND_ROLE) == "folder" and self._is_simulation_directory(
            Path(item.data(self.PATH_ROLE))
        ):
            for row in range(item.rowCount()):
                child = item.child(row)
                if child.data(self.KIND_ROLE) == "stage_group":
                    stage_index = self.proxy.mapFromSource(child.index())
                    if stage_index.isValid():
                        self.tree.expand(stage_index)
        self.tree.scrollTo(index)
        parent = index.parent()
        while parent.isValid():
            self.tree.expand(parent)
            parent = parent.parent()
        return True

    def _show_result_context_menu(self, position):
        index = self.tree.indexAt(position)
        if not index.isValid():
            return
        source_index = self.proxy.mapToSource(index)
        raw_path = self.model.data(source_index, self.PATH_ROLE)
        if not raw_path:
            return
        path = Path(raw_path)
        menu = QtWidgets.QMenu(self.tree)
        open_action = menu.addAction("Open containing folder")
        copy_action = menu.addAction("Copy path")
        export_action = menu.addAction("Export current 3D view…")
        export_action.setEnabled(
            self.viewer is not None
            and path == self._selected_path
            and self.preview_stack.currentWidget() is self.molecular_page
        )
        chosen = menu.exec(self.tree.viewport().mapToGlobal(position))
        if chosen is open_action:
            folder = path if path.is_dir() else path.parent
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))
        elif chosen is copy_action:
            QtWidgets.QApplication.clipboard().setText(str(path))
        elif chosen is export_action:
            self._export_current_view()

    def _numeric_data_loaded(self, generation: int, path: Path, payload):
        if (
            not self._selection_is_current(generation, path)
            or self.data_plot is None
        ):
            return
        self.data_plot.set_dataset(payload)
        self.preview_stack.setCurrentWidget(self.data_plot)

    def _numeric_data_failed(self, generation: int, path: Path, message: str):
        if not self._selection_is_current(generation, path):
            return
        self._show_numeric_error(
            f"Could not analyze {path.name}",
            f"{message}\n\nUse ‘View text’ to inspect the raw file.",
        )

    @staticmethod
    def _molecular_kind(path: Path) -> str | None:
        try:
            with path.open("rb") as handle:
                head = handle.read(16_384).decode("utf-8", errors="replace")
        except OSError:
            return None
        if "ITEM: TIMESTEP" in head and "ITEM: ATOMS" in head:
            return "trajectory"
        lines = {line.partition("#")[0].strip() for line in head.splitlines()}
        if "Atoms" in lines and any(line.endswith(" atoms") for line in lines):
            return "structure"
        return None

    def _load_structure(self, path: Path, generation: int):
        from .molecular_viewer_3d import BackgroundWorker, scene_from_lammps_data

        self._stop_playback()
        self._set_molecular_controls_enabled(False)
        self._set_playback_controls_enabled(False)
        orders = self._bond_orders_for(path)
        worker = BackgroundWorker(
            lambda: (scene_from_lammps_data(path, bond_pair_orders=orders), bool(orders))
        )
        self._start_worker(
            worker,
            lambda payload: self._structure_loaded(generation, path, payload),
            lambda message: self._preview_failed(generation, path, message),
        )

    def _structure_loaded(self, generation: int, path: Path, payload):
        if not self._selection_is_current(generation, path) or self.viewer is None:
            return
        scene, has_orders = payload
        try:
            self.viewer.set_scene(scene)
        except Exception as exc:
            self._preview_failed(generation, path, f"OpenGL upload failed: {exc}")
            return
        note = (
            "Scymol bond orders"
            if has_orders
            else "order-1 bond display" if scene.chemical_bond_count else "atoms only"
        )
        self.molecular_summary.setText(
            f"{path.name} · {len(scene.atom_data):,} atoms · "
            f"{scene.chemical_bond_count:,} bonds · {note}"
        )
        self.reset_button.setEnabled(True)
        self.pbc_checkbox.setEnabled(bool(scene.chemical_bond_count))
        self._set_molecular_controls_enabled(True)
        self._set_playback_controls_enabled(False)

    def _load_trajectory(self, path: Path, generation: int):
        from .molecular_viewer_3d import (
            BackgroundWorker,
            LammpsDumpTrajectory,
            scene_from_dump_frame,
            scene_from_lammps_data,
        )

        self._stop_playback()
        self._set_molecular_controls_enabled(False)
        self._set_playback_controls_enabled(False)
        structure = self._paired_structure(path)
        orders = self._bond_orders_for(structure) if structure else {}

        def load():
            trajectory = LammpsDumpTrajectory(path).build_index()
            frame = trajectory.load_frame(0)
            if structure:
                scene = scene_from_lammps_data(structure, bond_pair_orders=orders)
            else:
                scene = scene_from_dump_frame(frame, path.name)
            return trajectory, frame, scene, structure, bool(orders)

        worker = BackgroundWorker(load)
        self._start_worker(
            worker,
            lambda payload: self._trajectory_loaded(generation, path, payload),
            lambda message: self._preview_failed(generation, path, message),
        )

    def _trajectory_loaded(self, generation: int, path: Path, payload):
        if not self._selection_is_current(generation, path) or self.viewer is None:
            return
        trajectory, frame, scene, structure, has_orders = payload
        try:
            self.viewer.set_scene(scene)
            self.viewer.set_trajectory_frame(frame)
        except Exception as exc:
            self._preview_failed(generation, path, str(exc))
            return
        self._trajectory = trajectory
        self._requested_frame = 0
        self._frame_loading = False
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, len(trajectory.frames) - 1)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(len(trajectory.frames) > 1)
        self._set_frame_label(0)
        if structure:
            bond_note = "Scymol bond orders" if has_orders else "order-1 bond display"
            topology = f"topology: {structure.name} · {bond_note}"
        else:
            topology = "atoms only · no structure/topology paired"
        self.molecular_summary.setText(
            f"{path.name} · {len(trajectory.frames):,} frames · "
            f"{len(scene.atom_data):,} atoms · {topology}"
        )
        self.reset_button.setEnabled(True)
        self.pbc_checkbox.setEnabled(bool(structure and scene.chemical_bond_count))
        self._set_molecular_controls_enabled(True)
        self._set_playback_controls_enabled(len(trajectory.frames) > 1)

    def _queue_frame(self, index: int):
        if self._trajectory is None:
            return
        self._requested_frame = int(index)
        self._set_frame_label(index)
        if not self._frame_loading:
            self._load_requested_frame()

    def _load_requested_frame(self):
        if self._trajectory is None or self._requested_frame < 0:
            return
        from .molecular_viewer_3d import BackgroundWorker

        trajectory = self._trajectory
        index = self._requested_frame
        generation = self._preview_generation
        path = self._selected_path
        self._frame_loading = True
        worker = BackgroundWorker(lambda: (trajectory, trajectory.load_frame(index)))
        self._start_worker(
            worker,
            lambda payload: self._frame_loaded(generation, path, index, payload),
            lambda message: self._frame_load_failed(generation, path, message),
        )

    def _frame_loaded(self, generation, path, index, payload):
        if not self._selection_is_current(generation, path) or self.viewer is None:
            return
        trajectory, frame = payload
        if trajectory is not self._trajectory:
            return
        self._frame_loading = False
        try:
            self.viewer.set_trajectory_frame(frame)
        except Exception as exc:
            self._preview_failed(generation, path, str(exc))
            return
        self._set_frame_label(index)
        if self._requested_frame != index:
            self._load_requested_frame()

    def _frame_load_failed(self, generation, path, message: str):
        if not self._selection_is_current(generation, path):
            return
        self._frame_loading = False
        self._preview_failed(generation, path, message)

    def _set_playback_controls_enabled(self, enabled: bool):
        active = bool(enabled and self._trajectory is not None)
        for control in (
            self.previous_frame_button,
            self.play_button,
            self.next_frame_button,
            self.playback_speed,
        ):
            control.setEnabled(active)
        if not active:
            self._stop_playback()

    def _step_frame(self, delta: int):
        if self._trajectory is None or not self._trajectory.frames:
            return
        target = max(
            0,
            min(self.frame_slider.maximum(), self.frame_slider.value() + int(delta)),
        )
        self.frame_slider.setValue(target)

    def _toggle_playback(self, playing: bool):
        if playing and self._trajectory is not None and len(self._trajectory.frames) > 1:
            if self.frame_slider.value() >= self.frame_slider.maximum():
                self.frame_slider.setValue(0)
            self.play_button.setText("Pause")
            self.playback_timer.start()
        else:
            self.play_button.setText("Play")
            self.playback_timer.stop()

    def _stop_playback(self):
        if not hasattr(self, "play_button"):
            return
        self.play_button.blockSignals(True)
        self.play_button.setChecked(False)
        self.play_button.blockSignals(False)
        self.play_button.setText("Play")
        if hasattr(self, "playback_timer"):
            self.playback_timer.stop()

    def _update_playback_speed(self, *_):
        speed = float(self.playback_speed.currentData() or 1.0)
        if hasattr(self, "playback_timer"):
            self.playback_timer.setInterval(max(16, round(100.0 / speed)))

    def _advance_playback(self):
        if self._trajectory is None or self.frame_slider.value() >= self.frame_slider.maximum():
            self._stop_playback()
            return
        self.frame_slider.setValue(self.frame_slider.value() + 1)

    def _set_frame_label(self, index: int):
        if self._trajectory is None:
            return
        info = self._trajectory.frames[index]
        self.frame_label.setText(
            f"Frame {index + 1:,}/{len(self._trajectory.frames):,} · "
            f"step {info.timestep:,}"
        )

    def _paired_structure(self, trajectory: Path) -> Path | None:
        for name in (
            "structure.data",
            "source_structure_last_frame.data",
            "trajectory_snapshot.data",
            "source_structure.data",
        ):
            candidate = trajectory.parent / name
            if candidate.is_file() and self._molecular_kind(candidate) == "structure":
                return candidate
        return None

    def _bond_orders_for(self, structure: Path | None):
        if structure is None:
            return {}
        candidates = [structure.parent / "structure_manifest.json"]
        try:
            relative = structure.resolve().relative_to(self.root.resolve())
        except (OSError, ValueError):
            relative = None
        base_structure = self.root / "structure" / "structure.data"
        is_base = structure.resolve() == base_structure.resolve()
        is_simulation_copy = bool(
            structure.name == "structure.data"
            and any(
                (parent / "run_manifest.json").is_file()
                for parent in structure.parents
            )
        )
        if is_base or is_simulation_copy:
            project_metadata = self.root / "structure" / "structure_manifest.json"
            if project_metadata not in candidates:
                candidates.append(project_metadata)
        if relative and relative.parts[:2] == ("system", "imported"):
            candidates.append(self.root / "system" / "system_manifest.json")
        for metadata in candidates:
            try:
                payload = json.loads(metadata.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            records = list(payload.get("viewer_bond_orders", []))
            records.extend(
                record
                for molecule in payload.get("molecules", [])
                for record in molecule.get("viewer_bond_orders", [])
            )
            orders = {}
            for record in records:
                try:
                    first, second = (int(value) for value in record["atoms"])
                    orders[tuple(sorted((first, second)))] = record.get("order", 1.0)
                except (KeyError, TypeError, ValueError):
                    continue
            if orders:
                return orders
        return {}

    def _start_worker(self, worker, on_result, on_error):
        self._workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(lambda item=worker: self._workers.discard(item))
        QtCore.QThreadPool.globalInstance().start(worker)

    def _selection_is_current(self, generation: int, path: Path | None):
        return generation == self._preview_generation and path == self._selected_path

    def _preview_failed(self, generation: int, path: Path | None, message: str):
        if not self._selection_is_current(generation, path):
            return
        name = path.name if path else "file"
        self.molecular_summary.setText(f"Could not display {name}: {message}")
        self._set_molecular_controls_enabled(False)
        self._set_playback_controls_enabled(False)
        self.pbc_checkbox.setEnabled(False)

    def _show_text(self, path: Path):
        try:
            if path.stat().st_size > 2_000_000:
                self.preview.setPlainText(f"{path}\n\nFile is too large for an inline text preview.")
            else:
                self.preview.setPlainText(path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            self.preview.setPlainText(f"Cannot preview {path}\n\n{exc}")

    def _set_pbc(self, enabled: bool):
        if self.viewer is not None:
            self.viewer.set_pbc_enabled(enabled)

    def _set_molecular_controls_enabled(self, enabled: bool):
        available = bool(enabled and self.viewer is not None)
        for control in (
            self.reset_button,
            self.view_button,
            self.display_button,
            self.export_view_button,
        ):
            control.setEnabled(available)

    def _set_camera_view(self, name: str):
        if self.viewer is not None:
            self.viewer.set_camera_view(name)

    def _set_atoms_visible(self, visible: bool):
        if self.viewer is not None:
            self.viewer.set_atoms_visible(visible)

    def _set_bonds_visible(self, visible: bool):
        if self.viewer is not None:
            self.viewer.set_bonds_visible(visible)

    def _set_box_visible(self, visible: bool):
        if self.viewer is not None:
            self.viewer.set_box_visible(visible)

    def _export_current_view(self):
        if self.viewer is None:
            return
        selected = self._selected_path
        directory = selected.parent if selected else self.root
        stem = selected.stem if selected else "scymol"
        filename, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save 3D view",
            str(directory / f"{stem}_view.png"),
            "PNG image (*.png)",
        )
        target = Path(filename) if filename else None
        if target is not None and target.suffix.lower() != ".png":
            target = target.with_suffix(".png")
        if target is not None and not self.viewer.save_view(target):
            QtWidgets.QMessageBox.warning(
                self, "Could not save image", f"The image could not be written to:\n{target}"
            )

    def _reset_camera(self):
        if self.viewer is not None:
            self.viewer.reset_camera()

    def open_root(self):
        self.root.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.root)))
