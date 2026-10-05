from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable

from PySide6 import QtCore, QtWidgets

from .lammps_setup import load_lammps_configuration, lammps_status_text


class StartupDialog(QtWidgets.QDialog):
    """Application launcher for choosing how to enter the Scymol workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice = ""
        self.setWindowTitle("Start Scymol")
        self.setModal(True)
        self.setMinimumWidth(680)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)
        title = QtWidgets.QLabel("What would you like to do?")
        title.setObjectName("pageTitle")
        text = QtWidgets.QLabel(
            "Create a new Scymol project or continue working from an existing one."
        )
        text.setObjectName("pageDescription")
        text.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(text)

        new_project = QtWidgets.QPushButton(
            "New Project\n\nCreate and name a new Scymol workspace"
        )
        open_project = QtWidgets.QPushButton(
            "Open Project\n\nResume an existing Scymol workspace"
        )
        for button in (new_project, open_project):
            button.setObjectName("startupChoiceButton")
            button.setMinimumSize(280, 150)
            button.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Fixed,
            )
        tutorial_prompt = QtWidgets.QLabel("Not sure where to begin?")
        tutorial_prompt.setObjectName("sectionTitle")
        tutorial_prompt.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        tutorial = QtWidgets.QPushButton("Start the guided 50-benzene tutorial")
        tutorial.setObjectName("primaryButton")
        later = QtWidgets.QPushButton("Not now")
        later.setFlat(True)
        tutorial.clicked.connect(lambda: self._choose("tutorial"))
        new_project.clicked.connect(lambda: self._choose("new"))
        open_project.clicked.connect(lambda: self._choose("open"))
        later.clicked.connect(self.reject)
        choices = QtWidgets.QHBoxLayout()
        choices.setSpacing(14)
        choices.addWidget(new_project)
        choices.addWidget(open_project)
        layout.addLayout(choices)

        lammps_box = QtWidgets.QGroupBox("LAMMPS execution")
        lammps_layout = QtWidgets.QHBoxLayout(lammps_box)
        configuration = load_lammps_configuration()
        lammps_status = QtWidgets.QLabel(lammps_status_text(configuration))
        lammps_status.setObjectName("stageStatus")
        lammps_status.setProperty(
            "state", "complete" if configuration.available else "pending"
        )
        lammps_status.setWordWrap(True)
        configure_lammps = QtWidgets.QPushButton(
            "Reconfigure…" if configuration.available else "Configure…"
        )
        configure_lammps.clicked.connect(lambda: self._choose("configure_lammps"))
        lammps_layout.addWidget(lammps_status, 1)
        lammps_layout.addWidget(configure_lammps)
        layout.addWidget(lammps_box)

        layout.addSpacing(8)
        layout.addWidget(tutorial_prompt)
        layout.addWidget(tutorial)
        layout.addWidget(later)

    def _choose(self, choice: str):
        self.choice = choice
        self.accept()


class NewProjectDialog(QtWidgets.QDialog):
    """Name a project and choose its initial system-entry workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_name = ""
        self.source_mode = "build"
        self.project_directory: Path | None = None
        self.setWindowTitle("Create a new Scymol project")
        self.setModal(True)
        self.setMinimumWidth(940)

        documents = QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.DocumentsLocation
        )
        documents_root = Path(documents) if documents else Path.home() / "Documents"
        self.projects_root = documents_root / "Scymol Projects"

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)
        title = QtWidgets.QLabel("New Project")
        title.setObjectName("pageTitle")
        description = QtWidgets.QLabel(
            "Name the project, then choose how its molecular system should begin. "
            "Scymol creates and saves the project automatically."
        )
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        form = QtWidgets.QFormLayout()
        self.name_editor = QtWidgets.QLineEdit()
        self.name_editor.setPlaceholderText("For example: Benzene at 298 K")
        self.name_editor.setMaxLength(100)
        form.addRow("Project name", self.name_editor)
        layout.addLayout(form)

        prompt = QtWidgets.QLabel("How would you like to define the system?")
        prompt.setObjectName("sectionTitle")
        layout.addWidget(prompt)
        self.draw_choice = QtWidgets.QPushButton(
            "Draw a new system\n\nSketch molecular species and set their counts"
        )
        self.import_choice = QtWidgets.QPushButton(
            "Import an existing system\n\nUse a LAMMPS structure, trajectory, or both"
        )
        self.merge_choice = QtWidgets.QPushButton(
            "Merge existing systems\n\nCombine LAMMPS data geometries, then reparameterize"
        )
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for button in (self.draw_choice, self.import_choice, self.merge_choice):
            button.setObjectName("sourceChoiceButton")
            button.setCheckable(True)
            button.setMinimumHeight(105)
            self.mode_group.addButton(button)
        self.draw_choice.setChecked(True)
        modes = QtWidgets.QHBoxLayout()
        modes.setSpacing(12)
        modes.addWidget(self.draw_choice)
        modes.addWidget(self.import_choice)
        modes.addWidget(self.merge_choice)
        layout.addLayout(modes)

        location_title = QtWidgets.QLabel("Project location")
        location_title.setObjectName("sectionTitle")
        self.location = QtWidgets.QLabel()
        self.location.setObjectName("note")
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(location_title)
        layout.addWidget(self.location)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.create_button = buttons.addButton(
            "Create project", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.create_button.setObjectName("primaryButton")
        self.create_button.setEnabled(False)
        buttons.rejected.connect(self.reject)
        self.create_button.clicked.connect(self._create)
        layout.addWidget(buttons)

        self.name_editor.textChanged.connect(self._name_changed)
        self.name_editor.returnPressed.connect(
            lambda: self._create() if self.create_button.isEnabled() else None
        )
        self.name_editor.setFocus()
        self._name_changed("")

    def _name_changed(self, text: str):
        name = text.strip()
        self.create_button.setEnabled(bool(name))
        self.location.setText(str(self._available_directory(name or "Untitled project")))

    def _available_directory(self, name: str) -> Path:
        folder = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" ._")
        folder = folder[:80] or "Untitled project"
        reserved = {
            "con", "prn", "aux", "nul",
            *(f"com{i}" for i in range(1, 10)),
            *(f"lpt{i}" for i in range(1, 10)),
        }
        if folder.lower() in reserved:
            folder = f"Scymol {folder}"
        candidate = self.projects_root / folder
        suffix = 2
        while candidate.exists():
            candidate = self.projects_root / f"{folder} {suffix}"
            suffix += 1
        return candidate

    def _create(self):
        name = self.name_editor.text().strip()
        if not name:
            return
        self.project_name = name
        self.source_mode = (
            "merge" if self.merge_choice.isChecked()
            else "import" if self.import_choice.isChecked()
            else "build"
        )
        self.project_directory = self._available_directory(name)
        self.accept()


@dataclass(frozen=True)
class TutorialStep:
    tab: int
    title: str
    text: str
    target: Callable[[], QtWidgets.QWidget | None]
    complete: Callable[[], bool]
    optional: bool = False


class TutorialPanel(QtWidgets.QWidget):
    backRequested = QtCore.Signal()
    nextRequested = QtCore.Signal()
    stopRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        self.progress = QtWidgets.QLabel()
        self.progress.setObjectName("tutorialProgress")
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("sectionTitle")
        self.title.setWordWrap(True)
        self.text = QtWidgets.QLabel()
        self.text.setWordWrap(True)
        self.requirement = QtWidgets.QLabel()
        self.requirement.setObjectName("note")
        self.requirement.setWordWrap(True)
        layout.addWidget(self.progress)
        layout.addWidget(self.title)
        layout.addWidget(self.text)
        layout.addWidget(self.requirement)
        layout.addStretch()

        controls = QtWidgets.QHBoxLayout()
        self.stop_button = QtWidgets.QPushButton("Exit guide")
        self.stop_button.setFlat(True)
        self.back_button = QtWidgets.QPushButton("Back")
        self.next_button = QtWidgets.QPushButton("Next")
        self.next_button.setObjectName("primaryButton")
        controls.addWidget(self.stop_button)
        controls.addStretch()
        controls.addWidget(self.back_button)
        controls.addWidget(self.next_button)
        layout.addLayout(controls)
        self.stop_button.clicked.connect(self.stopRequested.emit)
        self.back_button.clicked.connect(self.backRequested.emit)
        self.next_button.clicked.connect(self.nextRequested.emit)


class TutorialWindow(QtWidgets.QDialog):
    """Prominent, modeless coach that stays above the window it is teaching."""

    def __init__(self, panel: TutorialPanel, parent=None):
        super().__init__(parent)
        self.setObjectName("tutorialWindow")
        self.setWindowTitle("Scymol guided tutorial")
        self.setModal(False)
        self.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowTitleHint
            | QtCore.Qt.WindowType.CustomizeWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(430, 330)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel)


class TutorialController(QtCore.QObject):
    """A prominent coach that advances from real workflow completion state."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.index = 0
        self.active = False
        self.highlighted: QtWidgets.QWidget | None = None
        self.panel = TutorialPanel()
        self.dialog = TutorialWindow(self.panel, window)
        self.dialog.hide()

        self.steps = [
            TutorialStep(
                0,
                "1. Confirm the molecular system",
                "Benzene is already drawn as one species with a count of 50. Select it "
                "on the canvas to inspect its SMILES and count, then click Validate and continue.",
                lambda: window.system_page.canvas_box,
                lambda: self._page_complete(window.system_page),
            ),
            TutorialStep(
                1,
                "2. Build and inspect the structure",
                "The example starts packing at 30% of its 876 kg/m³ target density, with "
                "random orientations, GAFF2, and Gasteiger charges. Click Build 3-D and "
                "LAMMPS structure. Scymol will type benzene once and reuse it for the "
                "other 49 molecules.",
                lambda: window.structure_page,
                lambda: self._page_complete(window.structure_page),
            ),
            TutorialStep(
                2,
                "3. Review the 298.15 K protocol",
                "The starter graph initializes and minimizes the system, creates velocities, "
                "then runs NVT at 298.15 K. Select nodes to inspect their commands, then "
                "validate the protocol.",
                lambda: window.protocol_page.editor,
                lambda: self._page_complete(window.protocol_page),
            ),
            TutorialStep(
                3,
                "4. Prepare the simulation",
                "The protocol is the simulation. Click Prepare simulation to write its "
                "LAMMPS input and copy structure.data into the simulation folder.",
                lambda: window.runs_page.run_button,
                lambda: bool(window.runs_page.records),
            ),
            TutorialStep(
                3,
                "5. Run LAMMPS when available",
                "Select the prepared simulation. If LAMMPS is configured, open Execution settings, check "
                "the command, and click Run selected. You may continue without executing "
                "when LAMMPS is not installed on this computer.",
                lambda: window.runs_page.run_selected_button,
                lambda: True,
                optional=True,
            ),
            TutorialStep(
                4,
                "6. Explore the results",
                "Generated inputs are already visible here. After a simulation, select a "
                "trajectory for 3-D playback or a LAMMPS log/output file for Plot. That is "
                "the complete Scymol workflow.",
                lambda: window.results_page.tree_panel,
                lambda: True,
                optional=True,
            ),
        ]

        self.panel.backRequested.connect(self.back)
        self.panel.nextRequested.connect(self.next)
        self.panel.stopRequested.connect(self.stop)
        window.tabs.currentChanged.connect(self._tab_changed)
        for page in (
            window.system_page,
            window.structure_page,
            window.protocol_page,
            window.runs_page,
        ):
            page.statusChanged.connect(self.refresh)
        window.runs_page.recordsChanged.connect(self.refresh)

    @staticmethod
    def _page_complete(page) -> bool:
        return str(page.status.property("state")) == "complete"

    def start(self):
        self.active = True
        self.index = 0
        self.dialog.show()
        self.dialog.adjustSize()
        frame = self.window.frameGeometry()
        self.dialog.move(
            frame.center().x() - self.dialog.width() // 2,
            frame.top() + max(50, (frame.height() - self.dialog.height()) // 4),
        )
        self.dialog.raise_()
        self.dialog.activateWindow()
        self._show_step()

    def stop(self):
        self.active = False
        self._clear_highlight()
        self.dialog.hide()

    def back(self):
        if self.index > 0:
            self.index -= 1
            self._show_step()

    def next(self):
        step = self.steps[self.index]
        if not (step.complete() or step.optional):
            self.refresh()
            return
        if self.index == len(self.steps) - 1:
            self.stop()
            self.window.statusBar().showMessage("Guided tutorial completed.", 6000)
            return
        self.index += 1
        self._show_step()

    def refresh(self, *_):
        if not self.active:
            return
        step = self.steps[self.index]
        ready = bool(step.complete() or step.optional)
        self.panel.next_button.setEnabled(ready)
        self.panel.next_button.setText(
            "Finish" if self.index == len(self.steps) - 1 else "Next"
        )
        if step.optional:
            self.panel.requirement.setText("Optional step · continue whenever you are ready.")
        elif ready:
            self.panel.requirement.setText("Stage complete · continue to the next step.")
        else:
            self.panel.requirement.setText(
                "Complete the highlighted stage action to unlock the next step."
            )

    def _show_step(self, navigate: bool = True):
        step = self.steps[self.index]
        self.panel.progress.setText(f"Step {self.index + 1} of {len(self.steps)}")
        self.panel.title.setText(step.title)
        self.panel.text.setText(step.text)
        self.panel.back_button.setEnabled(self.index > 0)
        if navigate:
            self.window.tabs.setCurrentIndex(step.tab)
        self._highlight(step.target())
        self.refresh()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _highlight(self, widget: QtWidgets.QWidget | None):
        self._clear_highlight()
        self.highlighted = widget
        if widget is not None:
            widget.setProperty("tutorialTarget", True)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _clear_highlight(self):
        if self.highlighted is not None:
            self.highlighted.setProperty("tutorialTarget", False)
            self.highlighted.style().unpolish(self.highlighted)
            self.highlighted.style().polish(self.highlighted)
            self.highlighted = None

    def _tab_changed(self, tab: int):
        if not self.active or self.index >= len(self.steps) - 1:
            return
        current = self.steps[self.index]
        following = self.steps[self.index + 1]
        if tab == following.tab and (current.complete() or current.optional):
            self.index += 1
            self._show_step(navigate=False)
