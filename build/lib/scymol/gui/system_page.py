from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from PySide6 import QtCore, QtWidgets

from ..models import MergeSource, MoleculeSpec, ScymolProject, system_definition_signature
from ..system_import import read_lammps_structure
from .base import StagePage
from .molecule_drawer import MoleculeCanvas, SketchToolBar


class SystemSourceDialog(QtWidgets.QDialog):
    """One-time source choice shown before an empty project enters Stage 1."""

    def __init__(self, current_mode: str = "", parent=None):
        super().__init__(parent)
        self.selected_mode = ""
        self.setWindowTitle("Start the molecular system")
        self.setModal(True)
        self.setMinimumWidth(980)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)
        title = QtWidgets.QLabel("How would you like to start?")
        title.setObjectName("pageTitle")
        description = QtWidgets.QLabel(
            "Choose the source of the molecular system. Stage 1 will then show only the controls needed for that workflow."
        )
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)

        choices = QtWidgets.QHBoxLayout()
        choices.setSpacing(14)
        choices.addWidget(
            self._choice_card(
                "Create a molecular system",
                "Draw molecular species and set their counts. Coordinates and force-field typing are prepared in Stage 2.",
                "Start drawing",
                "build",
                current_mode == "build",
            )
        )
        choices.addWidget(
            self._choice_card(
                "Merge existing systems",
                "Translate and combine two or more LAMMPS data geometries, then reparameterize the complete result.",
                "Choose systems to merge",
                "merge",
                current_mode == "merge",
            )
        )
        choices.addWidget(
            self._choice_card(
                "Import an existing system",
                "Select a LAMMPS structure, trajectory, or both, then detect its molecular composition.",
                "Choose existing files",
                "import",
                current_mode == "import",
            )
        )
        root.addLayout(choices)

        later = QtWidgets.QPushButton("Decide later")
        later.setFlat(True)
        later.clicked.connect(self.reject)
        footer = QtWidgets.QHBoxLayout()
        footer.addStretch()
        footer.addWidget(later)
        root.addLayout(footer)

    def _choice_card(self, title, description, button_text, mode, current):
        card = QtWidgets.QFrame()
        card.setObjectName("sourceChoiceCard")
        card.setMinimumWidth(310)
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        heading = QtWidgets.QLabel(title)
        heading.setObjectName("sectionTitle")
        body = QtWidgets.QLabel(description)
        body.setWordWrap(True)
        button = QtWidgets.QPushButton(
            f"{button_text}{'  ·  Current' if current else ''}"
        )
        button.setObjectName("sourceChoiceButton")
        button.clicked.connect(lambda _checked=False, value=mode: self._choose(value))
        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addStretch()
        layout.addWidget(button)
        return card

    def _choose(self, mode: str):
        self.selected_mode = mode
        self.accept()


class SystemPage(StagePage):
    sourceModeRequested = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(
            "1 · System",
            "Define which molecular species are present and how many copies the system contains, or identify them from existing files.",
            "Validate and continue",
            parent,
        )
        self.compact_header()
        self.project: ScymolProject | None = None
        self.selected_species = -1
        self._loading = False
        self._loading_canvas = False
        self._metadata_history = []
        self._pending_metadata = None

        self.build_mode = QtWidgets.QRadioButton(self)
        self.import_mode = QtWidgets.QRadioButton(self)
        self.merge_mode = QtWidgets.QRadioButton(self)
        self.build_mode.hide()
        self.import_mode.hide()
        self.merge_mode.hide()
        self.source_mode_group = QtWidgets.QButtonGroup(self)
        self.source_mode_group.setExclusive(True)
        self.source_mode_group.addButton(self.build_mode)
        self.source_mode_group.addButton(self.import_mode)
        self.source_mode_group.addButton(self.merge_mode)
        self.build_mode.setChecked(True)

        self.source_bar = QtWidgets.QFrame()
        self.source_bar.setObjectName("sourceBar")
        source_bar_layout = QtWidgets.QHBoxLayout(self.source_bar)
        source_bar_layout.setContentsMargins(12, 8, 10, 8)
        self.source_mode_label = QtWidgets.QLabel()
        self.source_mode_label.setObjectName("sectionTitle")
        self.change_source_button = QtWidgets.QPushButton("Change input method…")
        source_bar_layout.addWidget(self.source_mode_label)
        source_bar_layout.addStretch()
        source_bar_layout.addWidget(self.change_source_button)
        self.layout.addWidget(self.source_bar)

        self.import_box = self._build_import_inputs()
        self.import_box.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.import_box.setVisible(False)
        self.layout.addWidget(self.import_box, 0)

        self.merge_box = self._build_merge_inputs()
        self.merge_box.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Maximum,
        )
        self.merge_box.setVisible(False)
        self.layout.addWidget(self.merge_box, 0)

        self.import_results_placeholder = QtWidgets.QGroupBox(
            "Detected molecular composition"
        )
        placeholder_layout = QtWidgets.QVBoxLayout(self.import_results_placeholder)
        self.placeholder_text = QtWidgets.QLabel(
            "Choose a LAMMPS structure, trajectory, or both above, then select "
            "Analyze and import. Detected molecular species and counts will appear "
            "here on the canvas."
        )
        self.placeholder_text.setObjectName("note")
        self.placeholder_text.setWordWrap(True)
        self.placeholder_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addStretch()
        placeholder_layout.addWidget(self.placeholder_text)
        placeholder_layout.addStretch()
        self.import_results_placeholder.setVisible(False)
        self.layout.addWidget(self.import_results_placeholder, 1)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.composition_splitter = splitter
        self.canvas_box = QtWidgets.QGroupBox("Molecular composition")
        canvas_layout = QtWidgets.QVBoxLayout(self.canvas_box)
        self.toolbar = SketchToolBar()
        self.canvas = MoleculeCanvas()
        self.canvas.setMinimumSize(520, 330)
        self.canvas.set_component_label_provider(self._component_label)
        self.canvas_hint = QtWidgets.QLabel("")
        self.canvas_hint.setObjectName("note")
        self.canvas_hint.setWordWrap(True)
        self.canvas_hint.setVisible(False)
        tool_row = QtWidgets.QHBoxLayout()
        tool_row.setContentsMargins(0, 0, 0, 0)
        tool_row.addWidget(self.toolbar, 1)
        self.active_tool_label = QtWidgets.QLabel("Active tool  ·  Atom C")
        self.active_tool_label.setObjectName("activeToolStatus")
        self.active_tool_label.setToolTip(
            "The next drag or placement action uses this sketching tool. A plain click selects."
        )
        tool_row.addWidget(self.active_tool_label)
        canvas_layout.addLayout(tool_row)
        self.canvas_error = QtWidgets.QLabel("")
        self.canvas_error.setObjectName("inlineValidation")
        self.canvas_error.setWordWrap(True)
        self.canvas_error.setProperty("state", "failed")
        self.canvas_error.setVisible(False)
        canvas_layout.addWidget(self.canvas_error)
        canvas_layout.addWidget(self.canvas, 1)
        canvas_layout.addWidget(self.canvas_hint)
        splitter.addWidget(self.canvas_box)
        splitter.addWidget(self._build_species_inspector())
        splitter.setSizes([850, 310])
        self.layout.addWidget(splitter, 1)
        self._connect_canvas()
        self.build_mode.toggled.connect(self._mode_changed)
        self.import_mode.toggled.connect(self._mode_changed)
        self.merge_mode.toggled.connect(self._mode_changed)
        self.change_source_button.clicked.connect(
            lambda: self.sourceModeRequested.emit("")
        )
        self.import_run_button.clicked.connect(self.runRequested.emit)
        self.structure_file.textChanged.connect(self._edited)
        self.trajectory_file.textChanged.connect(self._edited)
        self.structure_browse.clicked.connect(self._browse_structure)
        self.trajectory_browse.clicked.connect(self._browse_trajectory)
        self.merge_add_button.clicked.connect(self._add_merge_sources)
        self.merge_remove_button.clicked.connect(self._remove_merge_sources)
        self.merge_duplicate_button.clicked.connect(self._duplicate_merge_sources)
        self.merge_table.itemChanged.connect(self._merge_edited)
        self.merge_arrange_button.clicked.connect(self._arrange_merge_sources)
        self.merge_run_button.clicked.connect(self.runRequested.emit)
        self.name_edit.editingFinished.connect(self._inspector_changed)
        self.count_edit.valueChanged.connect(self._inspector_changed)
        self.smiles_edit.editingFinished.connect(self._smiles_edited)
        self.add_button.clicked.connect(self._add_species)
        self.duplicate_button.clicked.connect(self._duplicate_species)
        self.remove_button.clicked.connect(self._remove_species)
        self.correct_button.clicked.connect(self._convert_import_to_drawing)

    def _build_import_inputs(self):
        box = QtWidgets.QGroupBox("Existing system inputs")
        layout = QtWidgets.QVBoxLayout(box)
        form = QtWidgets.QFormLayout()
        self.structure_file = QtWidgets.QLineEdit()
        self.structure_file.setPlaceholderText("Optional LAMMPS structure.data with atoms and topology")
        self.structure_browse = QtWidgets.QPushButton("Browse…")
        structure_row = QtWidgets.QHBoxLayout()
        structure_row.addWidget(self.structure_file, 1)
        structure_row.addWidget(self.structure_browse)
        self.trajectory_file = QtWidgets.QLineEdit()
        self.trajectory_file.setPlaceholderText("Optional LAMMPS dump trajectory (*.lammpstrj)")
        self.trajectory_browse = QtWidgets.QPushButton("Browse…")
        trajectory_row = QtWidgets.QHBoxLayout()
        trajectory_row.addWidget(self.trajectory_file, 1)
        trajectory_row.addWidget(self.trajectory_browse)
        form.addRow("Structure", structure_row)
        form.addRow("Trajectory", trajectory_row)
        layout.addLayout(form)
        note = QtWidgets.QLabel(
            "Supply either file or both. Structure topology is authoritative. Scymol uses "
            "the last trajectory frame as the starting coordinates; with only a trajectory, "
            "it also infers connectivity from that frame."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.import_run_button = QtWidgets.QPushButton("Analyze and import")
        self.import_run_button.setObjectName("primaryButton")
        actions.addWidget(self.import_run_button)
        layout.addLayout(actions)
        return box

    def _build_merge_inputs(self):
        box = QtWidgets.QGroupBox("Systems to merge")
        layout = QtWidgets.QVBoxLayout(box)
        note = QtWidgets.QLabel(
            "Add two or more LAMMPS data files and translate each system in Å. "
            "Scymol preserves atomic geometry and bonds, but discards all imported "
            "force-field typing so Stage 2 can parameterize the merged topology once. "
            "This first reliable version accepts orthogonal boxes only."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.merge_table = QtWidgets.QTableWidget(0, 4)
        self.merge_table.setHorizontalHeaderLabels(["LAMMPS data file", "ΔX (Å)", "ΔY (Å)", "ΔZ (Å)"])
        self.merge_table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2, 3):
            self.merge_table.horizontalHeader().setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        self.merge_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.merge_table.setMinimumHeight(145)
        layout.addWidget(self.merge_table)
        source_actions = QtWidgets.QHBoxLayout()
        self.merge_add_button = QtWidgets.QPushButton("＋ Add LAMMPS data files…")
        self.merge_duplicate_button = QtWidgets.QPushButton("Duplicate selected")
        self.merge_remove_button = QtWidgets.QPushButton("Remove selected")
        source_actions.addWidget(self.merge_add_button)
        source_actions.addWidget(self.merge_duplicate_button)
        source_actions.addWidget(self.merge_remove_button)
        source_actions.addStretch()
        layout.addLayout(source_actions)
        placement = QtWidgets.QHBoxLayout()
        placement.addWidget(QtWidgets.QLabel("Sequential placement"))
        self.merge_axis = QtWidgets.QComboBox()
        self.merge_axis.addItems(["X", "Y", "Z"])
        self.merge_buffer = QtWidgets.QDoubleSpinBox()
        self.merge_buffer.setRange(0.0, 1_000_000.0)
        self.merge_buffer.setDecimals(3)
        self.merge_buffer.setValue(5.0)
        self.merge_buffer.setSuffix(" Å buffer")
        self.merge_arrange_button = QtWidgets.QPushButton("Arrange in file order")
        self.merge_arrange_button.setToolTip(
            "Translate every box after the preceding box along the selected axis, "
            "leaving the requested empty distance between box boundaries."
        )
        placement.addWidget(self.merge_axis)
        placement.addWidget(self.merge_buffer)
        placement.addWidget(self.merge_arrange_button)
        placement.addStretch()
        layout.addLayout(placement)
        warning = QtWidgets.QLabel(
            "Risk boundary: Scymol does not remove overlaps, repair periodic interfaces, "
            "or decide whether the translated systems are physically compatible."
        )
        warning.setObjectName("inlineValidation")
        warning.setProperty("state", "pending")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        actions = QtWidgets.QHBoxLayout()
        actions.addStretch()
        self.merge_run_button = QtWidgets.QPushButton("Analyze and merge")
        self.merge_run_button.setObjectName("primaryButton")
        actions.addWidget(self.merge_run_button)
        layout.addLayout(actions)
        return box

    def _build_species_inspector(self):
        box = QtWidgets.QGroupBox("Selected species")
        layout = QtWidgets.QVBoxLayout(box)
        self.selection_title = QtWidgets.QLabel("Select a molecule on the canvas")
        self.selection_title.setObjectName("sectionTitle")
        self.selection_title.setWordWrap(True)
        layout.addWidget(self.selection_title)
        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.count_edit = QtWidgets.QSpinBox()
        self.count_edit.setRange(1, 1_000_000_000)
        self.smiles_edit = QtWidgets.QLineEdit()
        self.formula_label = QtWidgets.QLabel("—")
        self.formula_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.confidence_label = QtWidgets.QLabel("—")
        form.addRow("Name", self.name_edit)
        form.addRow("Count", self.count_edit)
        form.addRow("SMILES", self.smiles_edit)
        form.addRow("Formula", self.formula_label)
        form.addRow("Chemistry", self.confidence_label)
        layout.addLayout(form)

        actions = QtWidgets.QGridLayout()
        self.add_button = QtWidgets.QPushButton("＋ Add species")
        self.duplicate_button = QtWidgets.QPushButton("Duplicate")
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.setObjectName("dangerButton")
        actions.addWidget(self.add_button, 0, 0, 1, 2)
        actions.addWidget(self.duplicate_button, 1, 0)
        actions.addWidget(self.remove_button, 1, 1)
        layout.addLayout(actions)

        self.correct_button = QtWidgets.QPushButton("Edit as a regenerated system")
        self.correct_button.setObjectName("primaryButton")
        self.correct_button.setToolTip(
            "Convert the detected species into an editable drawing and regenerate coordinates and topology."
        )
        layout.addWidget(self.correct_button)
        self.system_summary = QtWidgets.QLabel()
        self.system_summary.setObjectName("note")
        self.system_summary.setWordWrap(True)
        layout.addWidget(self.system_summary)
        layout.addStretch()
        return box

    def _connect_canvas(self):
        self.toolbar.symSelected.connect(self.canvas.set_atom_symbol)
        self.toolbar.chainModeSelected.connect(self.canvas.set_chain_mode)
        self.toolbar.cyclohexaneModeSelected.connect(self.canvas.set_cyclohexane_mode)
        self.toolbar.benzeneModeSelected.connect(self.canvas.set_benzene_mode)
        self.canvas.activeToolChanged.connect(self._active_tool_changed)
        self.toolbar.unitedAtomToggled.connect(self.canvas.set_united_atom_mode)
        self.toolbar.snapGridClicked.connect(self.canvas.snap_components_to_grid)
        self.toolbar.undoClicked.connect(self._undo_canvas)
        self.toolbar.cleanClicked.connect(self.canvas.clean_structure)
        self.toolbar.clearClicked.connect(self._clear_species)
        self.toolbar.copySmilesClicked.connect(self._copy_smiles)
        self.toolbar.pasteSmilesClicked.connect(self._paste_smiles)
        self.toolbar.savePngClicked.connect(lambda: self._save_canvas(False))
        self.toolbar.saveSvgClicked.connect(lambda: self._save_canvas(True))
        self.canvas.changed.connect(self._canvas_changed)
        self.canvas.componentSelected.connect(self._select_species)

    def _active_tool_changed(self, tool: str):
        if not self.build_mode.isChecked():
            self.active_tool_label.setText("Selection mode  ·  Imported composition")
            return
        label = {
            "chain": "Carbon chain",
            "cyclohexane": "Cyclohexane",
            "benzene": "Benzene",
        }.get(tool, f"Atom {self.canvas.active_sym}")
        self.active_tool_label.setText(f"Active tool  ·  {label}")

    def load_project(self, project: ScymolProject):
        self.project = project
        self._loading = True
        try:
            self.structure_file.setText(project.imported_structure_file)
            self.trajectory_file.setText(project.imported_trajectory_file)
            self._load_merge_sources()
            self.import_mode.setChecked(project.system_entry_mode == "import")
            self.merge_mode.setChecked(project.system_entry_mode == "merge")
            self.build_mode.setChecked(project.system_entry_mode == "build")
            self._load_canvas()
            self._apply_mode()
        finally:
            self._loading = False
        if self.has_system_result():
            total = sum(item.count for item in project.molecules)
            self.set_status(
                "Validated" if project.system_entry_mode == "build" else "Analyzed",
                "complete",
                f"{len(project.molecules)} species · {total} molecules · ready for Stage 2",
            )

    def refresh_detected(self):
        if not self.project:
            return
        self._load_canvas()
        self._apply_mode()

    def set_source_unconfigured(self):
        if self.project is not None:
            self.set_source_mode(self.project.system_entry_mode)

    def set_source_mode(self, mode: str):
        if mode not in {"build", "import", "merge"}:
            raise ValueError(f"Unknown system source mode: {mode}")
        was_loading = self._loading
        self._loading = True
        try:
            if self.project is not None:
                self.project.system_entry_mode = mode
                if mode == "build":
                    self.project.structure.source_mode = "generate"
                elif mode == "merge":
                    self.project.structure.source_mode = "parameterize"
            {
                "build": self.build_mode,
                "import": self.import_mode,
                "merge": self.merge_mode,
            }[mode].setChecked(True)
            self._apply_mode()
        finally:
            self._loading = was_loading
        if not was_loading:
            self._invalidate_definition()
            self.changed.emit()

    def has_system_result(self) -> bool:
        if not self.project:
            return False
        expected = system_definition_signature(self.project)
        saved = self.project.system_definition_signature
        if saved:
            return saved == expected
        if saved == "" or not self.project.project_file:
            return False
        # Backward compatibility for projects created before Stage 1 validation
        # was recorded independently of generated geometry.
        manifest_path = self.project.output_root / "system" / "system_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        valid = bool(manifest.get("entry_mode") in {"build", "import", "merge"}) and (
            manifest_path.with_name("system.pdb").is_file()
        )
        if valid:
            self.project.system_definition_signature = expected
        return valid

    def commit(self):
        if not self.project:
            return
        self.project.system_entry_mode = (
            "merge" if self.merge_mode.isChecked()
            else "import" if self.import_mode.isChecked()
            else "build"
        )
        self.project.imported_structure_file = self.structure_file.text().strip()
        self.project.imported_trajectory_file = self.trajectory_file.text().strip()
        self.project.merge_sources = self._merge_sources_from_table()

    def _load_canvas(self):
        if not self.project:
            return
        self._loading_canvas = True
        try:
            self.canvas_error.setVisible(False)
            missing = [item.name for item in self.project.molecules if not item.smiles.strip()]
            if missing:
                raise ValueError(
                    "No renderable SMILES was inferred for: " + ", ".join(missing)
                )
            self.canvas.load_smiles_list(
                [item.smiles for item in self.project.molecules]
            )
            if len(self.canvas.connected_components()) != len(self.project.molecules):
                raise ValueError(
                    "One or more detected species could not be reconstructed from SMILES."
                )
            # In import mode the detector is authoritative. Merely drawing its
            # read-only result must not canonicalize SMILES and invalidate the
            # signature that was just written by the importer.
            if self.project.system_entry_mode == "build":
                self._refresh_derived_fields()
            if self.project.molecules:
                self._select_canvas_component(0)
            else:
                self._select_species(-1)
            self._refresh_labels()
            self.canvas.history.clear()
            self._metadata_history.clear()
            self._pending_metadata = None
        except Exception as exc:
            self.canvas.clear_all()
            self._select_species(-1)
            self.canvas_error.setText(
                "Could not display the molecular composition: " + str(exc)
            )
            self.canvas_error.setVisible(True)
        finally:
            self._loading_canvas = False

    def _refresh_derived_fields(self):
        if not self.project or self.project.system_entry_mode != "build":
            return
        try:
            details = self.canvas.component_details()
        except Exception:
            return
        for molecule, detail in zip(self.project.molecules, details):
            molecule.smiles = detail["smiles"]
            molecule.formula = detail["formula"]
            if self.project.system_entry_mode == "build":
                molecule.bond_order_status = "drawn"

    def _canvas_changed(self):
        if self._loading_canvas or not self.project:
            return
        if not self.build_mode.isChecked():
            return
        try:
            details = self.canvas.component_details()
        except Exception as exc:
            self.system_summary.setText(f"Invalid molecular drawing: {exc}")
            return
        if self._pending_metadata is not None:
            existing = self._pending_metadata
            self._pending_metadata = None
        else:
            self._metadata_history.append(deepcopy(self.project.molecules))
            existing = self.project.molecules
        updated = []
        for index, detail in enumerate(details):
            if index < len(existing):
                molecule = existing[index]
                molecule.smiles = detail["smiles"]
                molecule.formula = detail["formula"]
                molecule.bond_order_status = "drawn"
            else:
                molecule = MoleculeSpec(
                    name=f"Molecule {index + 1}",
                    smiles=detail["smiles"],
                    count=1,
                    formula=detail["formula"],
                    bond_order_status="drawn",
                )
            updated.append(molecule)
        self.project.molecules = updated
        self.project.structure.source_mode = "generate"
        self._invalidate_definition()
        canvas_selection = self._canvas_selected_index()
        self.selected_species = (
            canvas_selection
            if canvas_selection >= 0
            else min(self.selected_species, len(updated) - 1)
        )
        self._refresh_labels()
        self._load_inspector()
        self._refresh_summary()
        self.changed.emit()

    def _component_label(self, index, _component):
        if not self.project or index >= len(self.project.molecules):
            return f"Molecule {index + 1}"
        molecule = self.project.molecules[index]
        formula = molecule.formula or molecule.smiles or "unknown"
        return f"{molecule.name} · {formula} · ×{molecule.count}"

    def _refresh_labels(self):
        self.canvas.set_component_label_provider(self._component_label)
        self._refresh_summary()

    def _select_species(self, index):
        self.selected_species = index if self.project and index < len(self.project.molecules) else -1
        self._load_inspector()

    def _select_canvas_component(self, index):
        components = self.canvas.connected_components()
        components.sort(key=lambda component: min(component))
        if 0 <= index < len(components):
            self.canvas.select_component(min(components[index]))
        else:
            self.canvas.clear_selection()

    def _canvas_selected_index(self):
        atom_id = self.canvas.selected_atom
        if atom_id is None:
            return -1
        components = self.canvas.connected_components()
        components.sort(key=lambda component: min(component))
        for index, component in enumerate(components):
            if atom_id in component:
                return index
        return -1

    def _load_inspector(self):
        valid = bool(self.project and 0 <= self.selected_species < len(self.project.molecules))
        editable = valid and self.build_mode.isChecked()
        for widget in (self.name_edit, self.count_edit, self.smiles_edit):
            widget.blockSignals(True)
        if valid:
            molecule = self.project.molecules[self.selected_species]
            self.selection_title.setText(molecule.name)
            self.name_edit.setText(molecule.name)
            self.count_edit.setValue(molecule.count)
            self.smiles_edit.setText(molecule.smiles)
            self.formula_label.setText(molecule.formula or "—")
            self.confidence_label.setText(molecule.bond_order_status or "drawn")
        else:
            self.selection_title.setText("Select a molecule on the canvas")
            self.name_edit.clear()
            self.count_edit.setValue(1)
            self.smiles_edit.clear()
            self.formula_label.setText("—")
            self.confidence_label.setText("—")
        for widget in (self.name_edit, self.count_edit, self.smiles_edit):
            widget.blockSignals(False)
            widget.setEnabled(editable)
        self.duplicate_button.setEnabled(editable)
        self.remove_button.setEnabled(editable)

    def _inspector_changed(self, *_):
        if self._loading or not self.project or self.selected_species < 0:
            return
        molecule = self.project.molecules[self.selected_species]
        molecule.name = self.name_edit.text().strip() or f"Molecule {self.selected_species + 1}"
        molecule.count = self.count_edit.value()
        self._invalidate_definition()
        self.selection_title.setText(molecule.name)
        self._refresh_labels()
        self.changed.emit()

    def _smiles_edited(self):
        if not self.project or self.selected_species < 0 or not self.build_mode.isChecked():
            return
        text = self.smiles_edit.text().strip()
        if not text or "." in text:
            self.system_summary.setText(
                "Enter one connected molecular species. Add disconnected species separately."
            )
            self._load_inspector()
            return
        smiles = [item.smiles for item in self.project.molecules]
        smiles[self.selected_species] = text
        self._loading_canvas = True
        try:
            self.canvas.prepare_smiles_mol(text)
            self._metadata_history.append(deepcopy(self.project.molecules))
            self.canvas.load_smiles_list(smiles)
            details = self.canvas.component_details()
            for molecule, detail in zip(self.project.molecules, details):
                molecule.smiles = detail["smiles"]
                molecule.formula = detail["formula"]
                molecule.bond_order_status = "drawn"
            self._invalidate_definition()
            self._select_canvas_component(self.selected_species)
            self._refresh_labels()
            self._load_inspector()
            self.changed.emit()
        except Exception as exc:
            self.system_summary.setText(f"Invalid SMILES: {exc}")
            self._load_inspector()
        finally:
            self._loading_canvas = False

    def _add_species(self):
        if not self.project or not self.build_mode.isChecked():
            return
        self.canvas.append_smiles("C")
        self._select_canvas_component(len(self.project.molecules) - 1)

    def _duplicate_species(self):
        if not self.project or not (0 <= self.selected_species < len(self.project.molecules)):
            return
        source = self.project.molecules[self.selected_species]
        self.canvas.append_smiles(source.smiles)
        duplicate = self.project.molecules[-1]
        duplicate.name = f"{source.name} copy"
        duplicate.count = source.count
        duplicate.formula = source.formula
        self._invalidate_definition()
        self._refresh_labels()
        self._select_canvas_component(len(self.project.molecules) - 1)
        self.changed.emit()

    def _remove_species(self):
        if not self.project or not (0 <= self.selected_species < len(self.project.molecules)):
            return
        index = self.selected_species
        previous = deepcopy(self.project.molecules)
        next_metadata = deepcopy(self.project.molecules)
        del next_metadata[index]
        self._metadata_history.append(previous)
        self._pending_metadata = next_metadata
        self.canvas.remove_component(index)
        self._select_canvas_component(min(index, len(self.project.molecules) - 1))

    def _clear_species(self):
        if not self.project or not self.build_mode.isChecked():
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Clear molecular composition?",
            "Remove every molecular species from the canvas?",
        )
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            self._metadata_history.append(deepcopy(self.project.molecules))
            self._pending_metadata = []
            self.canvas.clear_all()

    def _undo_canvas(self):
        if self._metadata_history:
            self._pending_metadata = self._metadata_history.pop()
        self.canvas.undo()

    def _copy_smiles(self):
        text = ".".join(item.smiles for item in self.project.molecules) if self.project else ""
        if text:
            QtWidgets.QApplication.clipboard().setText(text)
            self.system_summary.setText("Composition SMILES copied to the clipboard.")

    def _paste_smiles(self):
        if not self.build_mode.isChecked():
            return
        text, accepted = QtWidgets.QInputDialog.getText(
            self, "Add SMILES", "Enter one or more dot-separated molecular species:"
        )
        if not accepted or not text.strip():
            return
        try:
            additions = [smiles.strip() for smiles in text.split(".") if smiles.strip()]
            self.canvas.load_smiles_list(
                [item.smiles for item in self.project.molecules] + additions
            )
            self._select_canvas_component(len(self.project.molecules) - 1)
        except Exception as exc:
            self.system_summary.setText(f"Could not add SMILES: {exc}")

    def _save_canvas(self, svg):
        extension = "svg" if svg else "png"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            f"Save molecular composition as {extension.upper()}",
            f"molecular_composition.{extension}",
            f"{extension.upper()} files (*.{extension})",
        )
        if not path:
            return
        try:
            self.canvas.save_svg(path) if svg else self.canvas.save_png(path)
            self.system_summary.setText(f"Saved {path}")
        except Exception as exc:
            self.system_summary.setText(f"Could not save the canvas: {exc}")

    def _convert_import_to_drawing(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            "Edit detected chemistry?",
            "This converts the detected species into an editable definition. Stage 2 will then generate new coordinates and topology. Continue?",
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.build_mode.setChecked(True)
        if self.project:
            self.project.structure.source_mode = "generate"
        self._select_canvas_component(0 if self.project and self.project.molecules else -1)

    def _browse_structure(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select LAMMPS structure", "", "LAMMPS data files (*.data *.lmps);;All files (*)"
        )
        if path:
            self.structure_file.setText(path)

    def _browse_trajectory(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select LAMMPS trajectory", "", "LAMMPS trajectories (*.lammpstrj *.dump);;All files (*)"
        )
        if path:
            self.trajectory_file.setText(path)

    def _load_merge_sources(self):
        if not self.project:
            return
        blocker = QtCore.QSignalBlocker(self.merge_table)
        self.merge_table.setRowCount(0)
        for source in self.project.merge_sources:
            self._append_merge_source_row(source)
        del blocker

    def _append_merge_source_row(self, source: MergeSource):
        row = self.merge_table.rowCount()
        self.merge_table.insertRow(row)
        path_item = QtWidgets.QTableWidgetItem(source.path)
        path_item.setData(QtCore.Qt.ItemDataRole.UserRole, source.id)
        path_item.setFlags(path_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
        path_item.setToolTip(source.path)
        self.merge_table.setItem(row, 0, path_item)
        for column, value in enumerate(
            (source.shift_x, source.shift_y, source.shift_z), start=1
        ):
            item = QtWidgets.QTableWidgetItem(f"{float(value):.6g}")
            item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.merge_table.setItem(row, column, item)

    def _merge_sources_from_table(self):
        sources = []
        for row in range(self.merge_table.rowCount()):
            path_item = self.merge_table.item(row, 0)
            if path_item is None or not path_item.text().strip():
                continue
            values = []
            for column in (1, 2, 3):
                item = self.merge_table.item(row, column)
                try:
                    values.append(float(item.text()) if item else 0.0)
                except ValueError:
                    values.append(0.0)
            sources.append(
                MergeSource(
                    id=str(path_item.data(QtCore.Qt.ItemDataRole.UserRole) or "") or MergeSource().id,
                    path=path_item.text().strip(),
                    shift_x=values[0],
                    shift_y=values[1],
                    shift_z=values[2],
                )
            )
        return sources

    def _add_merge_sources(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select LAMMPS systems to merge",
            "",
            "LAMMPS data files (*.data *.lmps);;All files (*)",
        )
        if not paths:
            return
        blocker = QtCore.QSignalBlocker(self.merge_table)
        for path in paths:
            self._append_merge_source_row(MergeSource(path=path))
        del blocker
        self._edited()

    def _remove_merge_sources(self):
        rows = sorted(
            {index.row() for index in self.merge_table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not rows:
            return
        blocker = QtCore.QSignalBlocker(self.merge_table)
        for row in rows:
            self.merge_table.removeRow(row)
        del blocker
        self._edited()

    def _duplicate_merge_sources(self):
        rows = sorted(
            {index.row() for index in self.merge_table.selectionModel().selectedRows()}
        )
        if not rows:
            return
        current = self._merge_sources_from_table()
        blocker = QtCore.QSignalBlocker(self.merge_table)
        for row in rows:
            source = current[row]
            self._append_merge_source_row(
                MergeSource(
                    path=source.path,
                    shift_x=source.shift_x,
                    shift_y=source.shift_y,
                    shift_z=source.shift_z,
                )
            )
        del blocker
        self._edited()

    def _arrange_merge_sources(self):
        if self.merge_table.rowCount() < 2:
            QtWidgets.QMessageBox.information(
                self,
                "Sequential placement",
                "Add at least two LAMMPS data files first.",
            )
            return
        axis = self.merge_axis.currentIndex()
        column = axis + 1
        gap = self.merge_buffer.value()
        try:
            topologies = []
            for row in range(self.merge_table.rowCount()):
                path_item = self.merge_table.item(row, 0)
                path = Path(path_item.text().strip()) if path_item else Path()
                if not path.is_file():
                    raise ValueError(f"Merge source {row + 1} does not exist: {path}")
                topology = read_lammps_structure(path)
                if any(high <= low for low, high in topology.box):
                    raise ValueError(
                        f"Merge source {row + 1} has missing or invalid box bounds."
                    )
                topologies.append(topology)

            first_item = self.merge_table.item(0, column)
            try:
                first_shift = float(first_item.text()) if first_item else 0.0
            except ValueError:
                first_shift = 0.0
            cursor = topologies[0].box[axis][1] + first_shift
            blocker = QtCore.QSignalBlocker(self.merge_table)
            if first_item is not None:
                first_item.setText(f"{first_shift:.6g}")
                first_item.setBackground(QtCore.Qt.GlobalColor.transparent)
            for row, topology in enumerate(topologies[1:], start=1):
                low, high = topology.box[axis]
                shift = cursor + gap - low
                item = self.merge_table.item(row, column)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    self.merge_table.setItem(row, column, item)
                item.setText(f"{shift:.6g}")
                item.setBackground(QtCore.Qt.GlobalColor.transparent)
                cursor = high + shift
            del blocker
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self, "Could not arrange systems", str(exc)
            )
            return
        self._edited()
        self.set_status(
            "Placement updated",
            "pending",
            f"Systems arranged along {'XYZ'[axis]} with a {gap:g} Å box-to-box buffer. "
            "Review or fine-tune the translations before merging.",
        )

    def _merge_edited(self, item):
        blocker = QtCore.QSignalBlocker(self.merge_table)
        if item.column() in {1, 2, 3}:
            try:
                float(item.text())
                item.setBackground(QtCore.Qt.GlobalColor.transparent)
            except ValueError:
                item.setBackground(QtCore.Qt.GlobalColor.red)
        del blocker
        self._edited()

    def validate_merge_inputs(self):
        if self.merge_table.rowCount() < 2:
            raise ValueError("Add at least two LAMMPS data files to merge.")
        for row in range(self.merge_table.rowCount()):
            path_item = self.merge_table.item(row, 0)
            path = Path(path_item.text().strip()) if path_item else Path()
            if not path.is_file():
                raise ValueError(f"Merge source {row + 1} does not exist: {path}")
            for column, axis in zip((1, 2, 3), "XYZ"):
                item = self.merge_table.item(row, column)
                try:
                    float(item.text())
                except (AttributeError, ValueError):
                    raise ValueError(
                        f"Merge source {row + 1} has an invalid Δ{axis} translation."
                    ) from None

    def _mode_changed(self, checked):
        if not checked:
            return
        if self.build_mode.isChecked() and self.project and not self.canvas.model.atoms:
            self._load_canvas()
        self._apply_mode()
        self._edited()

    def _apply_mode(self):
        importing = self.import_mode.isChecked()
        merging = self.merge_mode.isChecked()
        external = importing or merging
        has_imported_results = self._has_imported_results()
        if external and not has_imported_results and self.canvas.model.atoms:
            self._loading_canvas = True
            try:
                self.canvas.load_smiles_list([])
                self._select_species(-1)
            finally:
                self._loading_canvas = False
        self.source_bar.setVisible(True)
        self.source_mode_label.setText(
            "Input method  ·  Merge existing systems"
            if merging
            else "Input method  ·  Existing system"
            if importing
            else "Input method  ·  Create a molecular system"
        )
        self.import_box.setVisible(importing)
        self.merge_box.setVisible(merging)
        self.placeholder_text.setText(
            "Add at least two LAMMPS data files above, position them with explicit "
            "translations, accept the risk boundary, then select Analyze and merge. "
            "Detected species will appear here."
            if merging
            else "Choose a LAMMPS structure, trajectory, or both above, then select "
            "Analyze and import. Detected molecular species and counts will appear "
            "here on the canvas."
        )
        self.import_results_placeholder.setVisible(
            external and not has_imported_results
        )
        self.composition_splitter.setVisible(not external or has_imported_results)
        self.canvas_box.setTitle(
            "Detected merged composition" if merging
            else "Detected molecular composition" if importing
            else "Molecular composition"
        )
        self.canvas.set_read_only(external)
        self.toolbar.setEnabled(not external)
        self.active_tool_label.setText(
            "Selection mode  ·  Detected composition"
            if external
            else "Active tool  ·  Atom C"
        )
        self.add_button.setEnabled(not external)
        self.correct_button.setVisible(external and has_imported_results and not merging)
        self.canvas_hint.setText(
            "Detected species are read-only. Select a molecule to inspect it, or convert the result into a regenerated drawing to correct its chemistry."
            if importing
            else "Merged species are read-only. Stage 2 preserves these coordinates and reparameterizes the complete topology."
            if merging
            else ""
        )
        self.canvas_hint.setVisible(external and has_imported_results)
        if self.run_button:
            self.run_button.setText("Validate and continue")
            self.run_button.setVisible(not external)
        self.import_run_button.setVisible(importing)
        self.merge_run_button.setVisible(merging)
        if self.status.text() == "Choose a source":
            self.set_status(
                "Ready",
                "pending",
                "Add and position the systems to merge."
                if merging
                else "Select existing files and analyze them."
                if importing
                else "Draw the molecular composition, then validate it for Stage 2.",
            )
        self._load_inspector()
        self._refresh_summary()

    def set_running(self, running: bool):
        super().set_running(running)
        self.import_run_button.setEnabled(not running)
        self.merge_run_button.setEnabled(not running)
        for widget in (
            self.merge_table,
            self.merge_add_button,
            self.merge_duplicate_button,
            self.merge_remove_button,
            self.merge_axis,
            self.merge_buffer,
            self.merge_arrange_button,
        ):
            widget.setEnabled(not running)
        self.change_source_button.setEnabled(not running)

    def _has_imported_results(self):
        manifest = self._import_manifest()
        if (
            not manifest
            or not self.project
            or manifest.get("entry_mode") != self.project.system_entry_mode
            or self.project.system_entry_mode not in {"import", "merge"}
        ):
            return False
        recorded_species = manifest.get("species", [])
        if not recorded_species:
            return bool(
                self.project.molecules
                and (self.project.output_root / "system" / "system.pdb").is_file()
            )
        current = [
            {
                "id": item.id,
                "name": item.name,
                "smiles": item.smiles,
                "formula": item.formula,
                "count": item.count,
                "bond_order_status": item.bond_order_status,
            }
            for item in self.project.molecules
        ]
        expected = [
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "smiles": item.get("smiles", ""),
                "formula": item.get("formula", ""),
                "count": item.get("count", 1),
                "bond_order_status": item.get("bond_order_status", ""),
            }
            for item in recorded_species
        ]
        return current == expected

    def _import_manifest(self):
        if not self.project or not self.project.project_file:
            return None
        manifest_path = self.project.output_root / "system" / "system_manifest.json"
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    def _import_results_current(self):
        if not self.project or not self._has_imported_results():
            return False
        manifest = self._import_manifest() or {}
        expected = system_definition_signature(self.project)
        return bool(
            self.project.system_definition_signature
            and self.project.system_definition_signature == expected
            and manifest.get("definition_signature") == expected
        )

    def _edited(self, *_):
        if self._loading:
            return
        self.commit()
        self._invalidate_definition()
        self._refresh_summary()
        self.changed.emit()

    def _invalidate_definition(self):
        if self.project is not None:
            self.project.system_definition_signature = ""
            if not self._loading:
                external = self.project.system_entry_mode in {"import", "merge"}
                self.set_status(
                    "Needs analysis" if external else "Needs validation",
                    "pending",
                    "Analyze the selected files again."
                    if external
                    else "Validate this molecular definition before preparing its 3-D structure.",
                )

    def _refresh_summary(self):
        if not self.project:
            return
        species_count = len(self.project.molecules)
        total = sum(item.count for item in self.project.molecules)
        external = self.import_mode.isChecked() or self.merge_mode.isChecked()
        if external:
            if not self._has_imported_results():
                self.system_summary.setText(
                    "Add systems and translations, then run Analyze and merge."
                    if self.merge_mode.isChecked()
                    else "Select existing-system inputs, then run Analyze and import."
                )
                return
            if not self._import_results_current():
                self.system_summary.setText(
                    f"Previous detected composition · {species_count} species · "
                    f"{total} total molecules · inputs changed; analyze again"
                )
                return
        mode = (
            "Merged composition" if self.merge_mode.isChecked()
            else "Imported composition" if self.import_mode.isChecked()
            else "Drawn composition"
        )
        self.system_summary.setText(f"{mode} · {species_count} species · {total} total molecules")
