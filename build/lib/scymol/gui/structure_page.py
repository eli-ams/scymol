from __future__ import annotations

import json
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from ..models import (
    ScymolProject,
    structure_build_signature,
    system_definition_signature,
)
from .base import StagePage


class StructurePage(StagePage):
    def __init__(self, parent=None):
        super().__init__(
            "2 · Structure",
            "Assign a force field and charges, define the simulation box, and generate a LAMMPS-ready structure.",
            "Build LAMMPS structure",
            parent,
        )
        self.compact_header()
        self.project: ScymolProject | None = None
        self._loading = False
        self._preview_signature = None
        self._preview_generation = 0
        self._preview_workers = set()
        self._viewer_import_error = ""
        self._generated_box_available = False
        self._imported_structure_origin = ""
        self._imported_geometry_available = False
        self._imported_forcefield_complete = False
        self._has_structure_input = False
        self._has_trajectory_input = False
        self._structure_stale = False

        controls = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 4, 0)

        source_box = QtWidgets.QGroupBox("Geometry choice")
        self.geometry_box = source_box
        source_layout = QtWidgets.QVBoxLayout(source_box)
        self.import_summary = QtWidgets.QLabel()
        self.import_summary.setObjectName("note")
        self.import_summary.setWordWrap(True)
        self.imported_source = QtWidgets.QRadioButton(
            "Preserve imported configuration"
        )
        self.generated_source = QtWidgets.QRadioButton(
            "Build geometry from the Stage 1 molecular definition"
        )
        self.generated_source.setChecked(True)
        self.source_note = QtWidgets.QLabel()
        self.source_note.setObjectName("note")
        self.source_note.setWordWrap(True)
        source_layout.addWidget(self.import_summary)
        source_layout.addWidget(self.imported_source)
        source_layout.addWidget(self.generated_source)
        source_layout.addWidget(self.source_note)
        controls_layout.addWidget(source_box)

        self.forcefield_mode_box = QtWidgets.QGroupBox("Force-field treatment")
        forcefield_mode_layout = QtWidgets.QVBoxLayout(self.forcefield_mode_box)
        self.keep_parameters = QtWidgets.QRadioButton(
            "Keep imported force-field parameters"
        )
        self.reparameterize = QtWidgets.QRadioButton(
            "Reparameterize without moving atoms"
        )
        self.forcefield_mode_note = QtWidgets.QLabel()
        self.forcefield_mode_note.setObjectName("note")
        self.forcefield_mode_note.setWordWrap(True)
        forcefield_mode_layout.addWidget(self.keep_parameters)
        forcefield_mode_layout.addWidget(self.reparameterize)
        forcefield_mode_layout.addWidget(self.forcefield_mode_note)
        controls_layout.addWidget(self.forcefield_mode_box)

        self.placement_box = QtWidgets.QGroupBox("3-D geometry and packing")
        placement_form = QtWidgets.QFormLayout(self.placement_box)
        self.target_density = QtWidgets.QDoubleSpinBox()
        self.target_density.setRange(0.001, 100000.0)
        self.target_density.setDecimals(3)
        self.target_density.setSuffix(" kg/m³")
        self.initial_density = QtWidgets.QDoubleSpinBox()
        self.initial_density.setRange(0.01, 100.0)
        self.initial_density.setDecimals(3)
        self.initial_density.setSuffix(" %")
        self.initial_density.setToolTip(
            "Fraction of the target density used for the initial, low-density packing box."
        )
        self.rotate_molecules = QtWidgets.QCheckBox("Randomly rotate molecule copies")
        self.rotate_molecules.setChecked(True)
        self.seed = QtWidgets.QSpinBox()
        self.seed.setRange(1, 2_147_483_647)
        placement_form.addRow("Target density", self.target_density)
        placement_form.addRow("Initial density", self.initial_density)
        placement_form.addRow("Orientation", self.rotate_molecules)
        placement_form.addRow("Random seed", self.seed)
        controls_layout.addWidget(self.placement_box)

        box = QtWidgets.QGroupBox("Force field and topology")
        self.parameter_box = box
        form = QtWidgets.QFormLayout(box)
        self.forcefield = QtWidgets.QComboBox()
        self.forcefield.setEditable(True)
        self.forcefield.addItems(["Gaff2", "Gaff", "Dreiding", "Pcff"])
        self.charges = QtWidgets.QComboBox()
        self.charges.setEditable(True)
        self.charges.addItems(["gasteiger", "default", "none"])
        self.padding = QtWidgets.QDoubleSpinBox()
        self.padding.setRange(0.0, 1000.0)
        self.padding.setDecimals(3)
        self.padding.setSuffix(" Å")
        self.boundary = QtWidgets.QLineEdit()
        self.atom_style = QtWidgets.QComboBox()
        self.atom_style.addItems(["full", "molecular", "charge", "atomic"])
        form.addRow("Force field", self.forcefield)
        form.addRow("Charge method", self.charges)
        form.addRow("Box padding", self.padding)
        form.addRow("Boundary", self.boundary)
        form.addRow("Atom style", self.atom_style)
        controls_layout.addWidget(box)

        self.files_toggle = QtWidgets.QToolButton()
        self.files_toggle.setText("Generated artifacts")
        self.files_toggle.setCheckable(True)
        self.files_toggle.setChecked(False)
        self.files_toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.files_toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        controls_layout.addWidget(self.files_toggle)
        self.files_panel = QtWidgets.QWidget()
        files_layout = QtWidgets.QFormLayout(self.files_panel)
        files_layout.setContentsMargins(10, 0, 0, 4)
        self.system_manifest = self._artifact_button()
        self.structure_data = self._artifact_button()
        self.metadata = self._artifact_button()
        files_layout.addRow("System manifest", self.system_manifest)
        files_layout.addRow("LAMMPS data", self.structure_data)
        files_layout.addRow("Structure metadata", self.metadata)
        self.files_panel.setVisible(False)
        controls_layout.addWidget(self.files_panel)
        note = QtWidgets.QLabel(
            "The structure builder uses RDKit and PySIMM when installed. Protocol editing remains available without them."
        )
        note.setObjectName("note")
        note.setWordWrap(True)
        controls_layout.addWidget(note)
        controls_layout.addStretch()

        preview_box = QtWidgets.QGroupBox("3D structure preview")
        preview_layout = QtWidgets.QVBoxLayout(preview_box)
        preview_toolbar = QtWidgets.QHBoxLayout()
        self.preview_summary = QtWidgets.QLabel("No structure loaded")
        self.preview_summary.setObjectName("note")
        self.preview_summary.setWordWrap(True)
        self.preview_reload = QtWidgets.QPushButton("Reload")
        self.preview_reset = QtWidgets.QPushButton("Reset")
        self.preview_reset.setToolTip("Reset to the fitted isometric camera")
        self.preview_view = QtWidgets.QPushButton("View")
        view_menu = QtWidgets.QMenu(self.preview_view)
        for label, camera_view in (
            ("Isometric", "isometric"),
            ("Front", "front"),
            ("Side", "side"),
            ("Top", "top"),
        ):
            action = view_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, name=camera_view: self._set_preview_view(name)
            )
        self.preview_view.setMenu(view_menu)
        self.preview_display = QtWidgets.QPushButton("Display")
        display_menu = QtWidgets.QMenu(self.preview_display)
        self.preview_atoms_action = display_menu.addAction("Atoms")
        self.preview_bonds_action = display_menu.addAction("Bonds")
        self.preview_box_action = display_menu.addAction("Simulation box")
        for action in (
            self.preview_atoms_action,
            self.preview_bonds_action,
            self.preview_box_action,
        ):
            action.setCheckable(True)
            action.setChecked(True)
        self.preview_display.setMenu(display_menu)
        self.preview_export = QtWidgets.QPushButton("PNG…")
        self.preview_export.setToolTip("Save the current antialiased 3D view as a PNG image")
        self.preview_maximize = QtWidgets.QPushButton("Maximize")
        self.preview_maximize.setCheckable(True)
        self.preview_pbc = QtWidgets.QCheckBox("Whole molecules")
        self.preview_pbc.setToolTip("Make bonded molecules whole across periodic boundaries")
        self.preview_pbc.setChecked(True)
        preview_layout.addWidget(self.preview_summary)
        preview_toolbar.addStretch(1)
        preview_toolbar.addWidget(self.preview_pbc)
        preview_toolbar.addWidget(self.preview_reset)
        preview_toolbar.addWidget(self.preview_view)
        preview_toolbar.addWidget(self.preview_display)
        preview_toolbar.addWidget(self.preview_export)
        preview_toolbar.addWidget(self.preview_reload)
        preview_toolbar.addWidget(self.preview_maximize)
        preview_layout.addLayout(preview_toolbar)

        self.preview_stack = QtWidgets.QStackedWidget()
        self.preview_stack.setMinimumSize(480, 430)
        self.preview_placeholder = QtWidgets.QLabel(
            "Build or load a LAMMPS structure to inspect it here."
        )
        self.preview_placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_placeholder.setWordWrap(True)
        self.preview_placeholder.setObjectName("note")
        self.preview_stack.addWidget(self.preview_placeholder)
        self.viewer = None
        try:
            from .molecular_viewer_3d import MolecularViewerWidget, empty_scene

            self.viewer = MolecularViewerWidget(
                self.preview_stack, scene=empty_scene(), embedded=True
            )
            self.preview_stack.addWidget(self.viewer)
        except (ImportError, RuntimeError) as exc:
            self._viewer_import_error = str(exc)
            self.preview_placeholder.setText(
                "3D preview is unavailable. Install NumPy and ModernGL, then restart Scymol.\n\n"
                + str(exc)
            )
        preview_layout.addWidget(self.preview_stack, 1)
        preview_hint = QtWidgets.QLabel(
            "Left drag: orbit · Right/middle drag: pan · Wheel: zoom · F: reset"
        )
        preview_hint.setObjectName("note")
        preview_layout.addWidget(preview_hint)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.controls_scroll = QtWidgets.QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.controls_scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.controls_scroll.setWidget(controls)
        self.controls_scroll.setMinimumWidth(340)
        splitter.addWidget(self.controls_scroll)
        splitter.addWidget(preview_box)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([390, 760])
        self.layout.addWidget(splitter, 1)

        self.forcefield.currentTextChanged.connect(self._edited)
        self.charges.currentTextChanged.connect(self._edited)
        self.padding.valueChanged.connect(self._edited)
        self.boundary.textChanged.connect(self._edited)
        self.atom_style.currentTextChanged.connect(self._edited)
        self.target_density.valueChanged.connect(self._edited)
        self.initial_density.valueChanged.connect(self._edited)
        self.rotate_molecules.toggled.connect(self._edited)
        self.seed.valueChanged.connect(self._edited)
        self.imported_source.toggled.connect(self._source_changed)
        self.keep_parameters.toggled.connect(self._source_changed)
        self.reparameterize.toggled.connect(self._source_changed)
        self.preview_reload.clicked.connect(lambda: self.refresh_preview(force=True))
        self.preview_reset.clicked.connect(self._reset_preview_camera)
        self.preview_export.clicked.connect(self._export_preview_image)
        self.preview_atoms_action.toggled.connect(self._set_preview_atoms)
        self.preview_bonds_action.toggled.connect(self._set_preview_bonds)
        self.preview_box_action.toggled.connect(self._set_preview_box)
        self.preview_pbc.toggled.connect(self._set_preview_pbc)
        self.preview_maximize.toggled.connect(self._toggle_preview_maximized)
        self.files_toggle.toggled.connect(self._toggle_artifacts)
        self.preview_reload.setEnabled(self.viewer is not None)
        self.preview_pbc.setEnabled(False)
        self._set_preview_controls_enabled(False)

    def _artifact_button(self):
        button = QtWidgets.QToolButton()
        button.setText("Not generated")
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setEnabled(False)
        button.clicked.connect(lambda _checked=False, item=button: self._open_artifact(item))
        return button

    def _set_artifact(self, button, path: Path, fallback: str = "Not generated", suffix: str = ""):
        exists = path.is_file()
        button.setProperty("artifactPath", str(path) if exists else "")
        button.setEnabled(exists)
        button.setText(f"{path.name}{suffix}" if exists else fallback)
        button.setToolTip(str(path))

    def _open_artifact(self, button):
        path = button.property("artifactPath")
        if path:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))

    def _toggle_artifacts(self, expanded: bool):
        self.files_toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )
        self.files_panel.setVisible(expanded)

    def _toggle_preview_maximized(self, maximized: bool):
        self.controls_scroll.setVisible(not maximized)
        self.preview_maximize.setText("Restore" if maximized else "Maximize")

    def load_project(self, project: ScymolProject):
        self.project = project
        self._loading = True
        try:
            self.forcefield.setCurrentText(project.structure.forcefield)
            self.charges.setCurrentText(project.structure.charges)
            self.padding.setValue(project.structure.box_padding_angstrom)
            self.boundary.setText(project.structure.boundary)
            self.atom_style.setCurrentText(project.structure.atom_style)
            self.target_density.setValue(project.system_target_density_kg_m3)
            self.initial_density.setValue(
                project.system_initial_density_fraction * 100.0
            )
            self.rotate_molecules.setChecked(project.system_rotate_molecules)
            self.seed.setValue(project.random_seed)
            self.refresh_files()
        finally:
            self._loading = False

    def commit(self):
        if not self.project:
            return
        if self.project.system_entry_mode == "merge":
            self.project.structure.source_mode = "parameterize"
        elif self.project.system_entry_mode != "import":
            self.project.structure.source_mode = "generate"
        elif self.generated_source.isChecked():
            self.project.structure.source_mode = "rebuild"
        elif self.keep_parameters.isChecked():
            self.project.structure.source_mode = "imported"
        else:
            self.project.structure.source_mode = "parameterize"
        self.project.structure.forcefield = self.forcefield.currentText().strip()
        self.project.structure.charges = self.charges.currentText().strip()
        self.project.structure.box_padding_angstrom = self.padding.value()
        self.project.structure.boundary = self.boundary.text().strip()
        self.project.structure.atom_style = self.atom_style.currentText()
        self.project.system_target_density_kg_m3 = self.target_density.value()
        self.project.system_initial_density_fraction = self.initial_density.value() / 100.0
        self.project.system_rotate_molecules = self.rotate_molecules.isChecked()
        self.project.random_seed = self.seed.value()

    def _edited(self, *_):
        if self._loading:
            return
        self.commit()
        self._update_structure_staleness()
        self.refresh_preview()
        if self._structure_stale:
            self.set_status(
                "Needs rebuild",
                "pending",
                "Stage 2 settings changed; rebuild to update structure.data.",
            )
        self.changed.emit()

    def _source_changed(self, *_):
        entry_mode = self.project.system_entry_mode if self.project else "build"
        importing = entry_mode == "import"
        merging = entry_mode == "merge"
        external = importing or merging
        preserve_geometry = external and (merging or self.imported_source.isChecked())
        rebuild_geometry = importing and self.generated_source.isChecked()
        if preserve_geometry and not (
            self.keep_parameters.isChecked() or self.reparameterize.isChecked()
        ):
            if self._imported_forcefield_complete and not merging:
                self.keep_parameters.setChecked(True)
            else:
                self.reparameterize.setChecked(True)
        creates_geometry = bool(
            self.project is not None
            and (self.project.system_entry_mode == "build" or rebuild_geometry)
        )
        keep_forcefield = bool(
            preserve_geometry
            and self.keep_parameters.isChecked()
            and self.keep_parameters.isEnabled()
        )
        self.forcefield_mode_box.setVisible(preserve_geometry)
        self.parameter_box.setEnabled(not keep_forcefield)
        self.placement_box.setEnabled(creates_geometry)
        self.padding.setEnabled(False)
        if self.run_button:
            self.run_button.setText(
                "Preserve configuration and imported parameters"
                if keep_forcefield
                else "Reparameterize merged geometry"
                if merging
                else "Reparameterize without moving atoms"
                if preserve_geometry
                else "Rebuild and parameterize mixture"
                if rebuild_geometry
                else "Build 3-D and LAMMPS structure"
            )
        if preserve_geometry:
            origin = (
                "the merged topology"
                if merging
                else
                "the last trajectory frame"
                if self._has_trajectory_input
                else "the imported LAMMPS data file"
            )
            self.source_note.setText(
                f"Keep the atomic positions and simulation box from {origin} exactly. "
                "Scymol will not generate conformers or repack the mixture."
            )
        elif rebuild_geometry:
            self.source_note.setText(
                "Use only the detected SMILES and molecule counts. Scymol will generate new "
                "conformers and Sobol-pack a completely new configuration. Imported positions "
                "and the imported box will not be used."
            )
        else:
            self.source_note.setText(
                "Generate conformers, Sobol-pack the requested composition, assign force-field "
                "types and write structure.data."
            )
        if self._imported_forcefield_complete:
            self.forcefield_mode_note.setText(
                "The imported data file contains reusable coefficients. You may keep them or "
                "replace them with the selected Scymol force field."
            )
        elif merging:
            self.forcefield_mode_note.setText(
                "All source force-field typing was intentionally discarded. The complete "
                "merged topology must be assigned one Scymol force field."
            )
        elif self._has_structure_input:
            self.forcefield_mode_note.setText(
                "The imported data file does not contain a complete reusable force field. "
                "Reparameterization is required; its topology and positions are still preserved."
            )
        else:
            self.forcefield_mode_note.setText(
                "A trajectory has no force-field coefficients. Scymol will use the bonds approved "
                "in Stage 1 and parameterize the preserved last-frame coordinates."
            )
        self._edited()

    def refresh_files(self):
        if not self.project:
            return
        self.atom_style.blockSignals(True)
        self.atom_style.setCurrentText(self.project.structure.atom_style)
        self.atom_style.blockSignals(False)
        system_manifest = self.project.output_root / "system" / "system_manifest.json"
        structure = self.project.output_root / "structure" / "structure.data"
        metadata = self.project.output_root / "structure" / "structure_manifest.json"
        self._set_artifact(self.system_manifest, system_manifest, "Pending Stage 2")
        self._update_structure_staleness()
        self._set_artifact(self.metadata, metadata)
        imported_available = False
        imported_forcefield_complete = False
        imported_timestep = None
        self._imported_structure_origin = ""
        self._has_structure_input = False
        self._has_trajectory_input = False
        self._generated_box_available = False
        if system_manifest.exists():
            try:
                manifest = json.loads(system_manifest.read_text(encoding="utf-8"))
                recorded_definition = manifest.get("definition_signature")
                manifest_current = not recorded_definition or (
                    recorded_definition == system_definition_signature(self.project)
                )
                if manifest_current:
                    self._generated_box_available = bool(
                        manifest.get("box")
                        or (
                            manifest.get("entry_mode") in {"import", "merge"}
                            and manifest.get("imported_structure")
                        )
                    )
                    self._imported_structure_origin = str(
                        manifest.get("imported_structure_origin", "")
                    )
                    imported_path = Path(manifest.get("imported_structure", ""))
                    imported_available = imported_path.is_file()
                    imported_forcefield_complete = bool(
                        manifest.get("imported_forcefield_complete")
                        if "imported_forcefield_complete" in manifest
                        else imported_available
                        and not manifest.get("direct_reuse_issues")
                    )
                    self._has_structure_input = bool(
                        manifest.get("has_structure_input")
                        or self._imported_structure_origin
                        in {"lammps_data", "structure_with_trajectory_snapshot"}
                    )
                    self._has_trajectory_input = bool(
                        manifest.get("has_trajectory_input")
                        or "trajectory_snapshot" in self._imported_structure_origin
                    )
                    imported_timestep = manifest.get("trajectory", {}).get(
                        "starting_timestep"
                    )
                else:
                    self._set_artifact(
                        self.system_manifest,
                        system_manifest,
                        "Pending Stage 2",
                        "  ·  stale",
                    )
            except (OSError, ValueError, TypeError):
                imported_available = False
        self._imported_geometry_available = imported_available
        self._imported_forcefield_complete = imported_forcefield_complete
        importing = self.project.system_entry_mode == "import"
        merging = self.project.system_entry_mode == "merge"
        external = importing or merging
        self.geometry_box.setTitle(
            "Merged geometry (fixed)"
            if merging
            else
            "Choose what Stage 2 should do with the imported system"
            if importing
            else "Geometry generation"
        )
        timestep_text = (
            f" (timestep {imported_timestep})"
            if imported_timestep is not None
            else ""
        )
        if merging:
            self.import_summary.setText(
                "Merged starting point: translated coordinates and bonded connectivity from "
                "all Stage 1 sources. Source types and coefficients will not be reused."
            )
        elif self._has_structure_input and self._has_trajectory_input:
            self.import_summary.setText(
                "Imported starting point: topology from structure.data and positions/box "
                f"from the last trajectory frame{timestep_text}."
            )
        elif self._has_trajectory_input:
            self.import_summary.setText(
                "Imported starting point: the last trajectory frame"
                f"{timestep_text}; "
                "bonds were inferred and reviewed in Stage 1."
            )
        elif self._has_structure_input:
            self.import_summary.setText(
                "Imported starting point: positions, box and topology from structure.data."
            )
        else:
            self.import_summary.setText(
                "No existing configuration was imported; Stage 2 will build one from the molecular definition."
            )
        self.imported_source.setVisible(external)
        self.imported_source.setEnabled(imported_available)
        self.imported_source.setText(
            "Preserve merged coordinates and topology"
            if merging
            else "Preserve imported configuration"
        )
        self.generated_source.setVisible(not merging)
        self.generated_source.setText(
            "Rebuild mixture from detected molecules"
            if importing
            else "Build geometry from the Stage 1 molecular definition"
        )
        mode = self.project.structure.source_mode
        preserve_geometry = external and imported_available and (merging or mode != "rebuild")
        blockers = [
            QtCore.QSignalBlocker(widget)
            for widget in (
                self.imported_source,
                self.generated_source,
                self.keep_parameters,
                self.reparameterize,
            )
        ]
        self.imported_source.setChecked(preserve_geometry)
        self.generated_source.setChecked(not preserve_geometry and not merging)
        self.keep_parameters.setVisible(not merging)
        self.keep_parameters.setEnabled(imported_forcefield_complete and not merging)
        keep_parameters = bool(
            preserve_geometry and imported_forcefield_complete and mode == "imported"
        )
        self.keep_parameters.setChecked(keep_parameters)
        self.reparameterize.setChecked(preserve_geometry and not keep_parameters)
        del blockers
        self._source_changed()
        if self._structure_stale:
            self.set_status(
                "Needs rebuild", "pending", "The previous structure does not match the current settings."
            )
        elif structure.exists():
            self.set_status("Complete", "complete", str(structure))
        elif (
            self.project.system_definition_signature
            == system_definition_signature(self.project)
        ):
            self.set_status(
                "Ready",
                "pending",
                "Build the 3-D geometry and LAMMPS structure.",
            )
        else:
            self.set_status(
                "Waiting for Stage 1",
                "pending",
                "Validate or analyze the molecular definition first.",
            )
        self.refresh_preview()
        available = sum(
            bool(button.property("artifactPath"))
            for button in (self.system_manifest, self.structure_data, self.metadata)
        )
        self.files_toggle.setText(f"Generated artifacts  ·  {available}/3")

    def _update_structure_staleness(self):
        if not self.project:
            return
        structure = self.project.output_root / "structure" / "structure.data"
        metadata = self.project.output_root / "structure" / "structure_manifest.json"
        self._structure_stale = False
        if structure.exists() and metadata.exists():
            try:
                payload = json.loads(metadata.read_text(encoding="utf-8"))
                recorded = payload.get("build_signature")
                self._structure_stale = bool(
                    recorded and recorded != structure_build_signature(self.project)
                )
            except (OSError, ValueError, TypeError):
                pass
        self._set_artifact(
            self.structure_data,
            structure,
            "Not generated",
            "  ·  STALE — rebuild required" if self._structure_stale else "",
        )

    def _viewer_bond_orders(self, metadata: Path) -> dict[tuple[int, int], float | str]:
        if not metadata.exists():
            return {}
        try:
            payload = json.loads(metadata.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        orders = {}
        for record in payload.get("viewer_bond_orders", []):
            try:
                first, second = (int(value) for value in record["atoms"])
                order = record.get("order", 1.0)
                orders[tuple(sorted((first, second)))] = order
            except (KeyError, TypeError, ValueError):
                continue
        return orders

    def refresh_preview(self, force: bool = False):
        if not self.project or self.viewer is None:
            return
        structure = self.project.output_root / "structure" / "structure.data"
        metadata = self.project.output_root / "structure" / "structure_manifest.json"
        if self._structure_stale:
            self._preview_generation += 1
            self._preview_signature = None
            self.preview_stack.setCurrentIndex(0)
            self.preview_placeholder.setText(
                "The molecular definition or Stage 2 settings changed.\n\n"
                "Build the structure again to update this preview."
            )
            self.preview_summary.setText("Previous structure is stale")
            self.preview_pbc.setEnabled(False)
            self._set_preview_controls_enabled(False)
            return
        if not structure.is_file():
            self._preview_generation += 1
            self._preview_signature = None
            self.preview_stack.setCurrentIndex(0)
            self.preview_summary.setText("No structure loaded")
            self.preview_pbc.setEnabled(False)
            self._set_preview_controls_enabled(False)
            return
        try:
            signature = (
                str(structure.resolve()),
                structure.stat().st_mtime_ns,
                structure.stat().st_size,
                metadata.stat().st_mtime_ns if metadata.exists() else 0,
            )
        except OSError as exc:
            self._preview_failed(self._preview_generation, str(exc))
            return
        if not force and signature == self._preview_signature:
            return

        from .molecular_viewer_3d import BackgroundWorker, scene_from_lammps_data

        self._preview_generation += 1
        generation = self._preview_generation
        orders = self._viewer_bond_orders(metadata)
        self.preview_reload.setEnabled(False)
        self.preview_pbc.setEnabled(False)
        self._set_preview_controls_enabled(False)
        self.preview_summary.setText(f"Loading {structure.name}…")
        self.preview_placeholder.setText("Reading coordinates and topology…")
        self.preview_stack.setCurrentIndex(0)
        worker = BackgroundWorker(
            lambda: (
                scene_from_lammps_data(structure, bond_pair_orders=orders),
                signature,
                bool(orders),
            )
        )
        self._preview_workers.add(worker)
        worker.signals.result.connect(
            lambda payload, token=generation: self._preview_loaded(token, payload)
        )
        worker.signals.error.connect(
            lambda message, token=generation: self._preview_failed(token, message)
        )
        worker.signals.finished.connect(lambda item=worker: self._preview_workers.discard(item))
        QtCore.QThreadPool.globalInstance().start(worker)

    def _preview_loaded(self, generation: int, payload):
        if generation != self._preview_generation or self.viewer is None:
            return
        scene, signature, has_orders = payload
        try:
            self.viewer.set_scene(scene)
        except Exception as exc:
            self._preview_failed(generation, f"OpenGL upload failed: {exc}")
            return
        self._preview_signature = signature
        self.preview_stack.setCurrentWidget(self.viewer)
        if scene.chemical_bond_count == 0:
            topology_note = "atoms only; no topology was available"
        elif has_orders:
            topology_note = "Scymol bond orders"
        else:
            topology_note = "topology shown with order-1 fallback"
        self.preview_summary.setText(
            f"{scene.label} · {len(scene.atom_data):,} atoms · "
            f"{scene.chemical_bond_count:,} bonds · {topology_note}"
        )
        self.preview_reload.setEnabled(True)
        self.preview_pbc.setEnabled(bool(scene.chemical_bond_count))
        self._set_preview_controls_enabled(True)

    def _preview_failed(self, generation: int, message: str):
        if generation != self._preview_generation:
            return
        detail = message.strip().splitlines()[-1] if message.strip() else "Unknown error"
        self.preview_placeholder.setText(f"Could not display this structure.\n\n{detail}")
        self.preview_stack.setCurrentIndex(0)
        self.preview_summary.setText("3D preview failed")
        self.preview_reload.setEnabled(True)
        self.preview_pbc.setEnabled(False)
        self._set_preview_controls_enabled(False)

    def _reset_preview_camera(self):
        if self.viewer is None:
            return
        self.viewer.reset_camera()

    def _set_preview_controls_enabled(self, enabled: bool):
        available = bool(enabled and self.viewer is not None)
        for control in (
            self.preview_reset,
            self.preview_view,
            self.preview_display,
            self.preview_export,
        ):
            control.setEnabled(available)

    def _set_preview_view(self, name: str):
        if self.viewer is not None:
            self.viewer.set_camera_view(name)

    def _set_preview_atoms(self, visible: bool):
        if self.viewer is not None:
            self.viewer.set_atoms_visible(visible)

    def _set_preview_bonds(self, visible: bool):
        if self.viewer is not None:
            self.viewer.set_bonds_visible(visible)

    def _set_preview_box(self, visible: bool):
        if self.viewer is not None:
            self.viewer.set_box_visible(visible)

    def _export_preview_image(self):
        if self.viewer is None:
            return
        directory = self.project.output_root / "structure" if self.project else Path.cwd()
        filename, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save 3D view",
            str(directory / "structure_view.png"),
            "PNG image (*.png)",
        )
        target = Path(filename) if filename else None
        if target is not None and target.suffix.lower() != ".png":
            target = target.with_suffix(".png")
        if target is not None and not self.viewer.save_view(target):
            QtWidgets.QMessageBox.warning(
                self, "Could not save image", f"The image could not be written to:\n{target}"
            )

    def _set_preview_pbc(self, enabled: bool):
        if self.viewer is not None:
            self.viewer.set_pbc_enabled(enabled)
