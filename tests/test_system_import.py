from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scymol.chemistry import build_structure
from scymol.models import MoleculeSpec, ScymolProject, system_definition_signature
from scymol.project_io import load_project, save_project
from scymol.system_import import assess_direct_reuse, read_first_lammps_frame, read_lammps_structure
from scymol.system_import import DetectedMolecule, import_existing_system

try:
    from PySide6 import QtWidgets
    from scymol.gui.structure_page import StructurePage
    from scymol.gui.system_page import SystemPage

    HAS_QT = True
except ImportError:
    HAS_QT = False


LAMMPS_DATA = """Imported ethane

2 atoms
1 bonds

1 atom types
1 bond types

0 20 xlo xhi
0 20 ylo yhi
0 20 zlo zhi

Masses

1 12.011 # C

Atoms # full

1 1 1 0.0 1.0 1.0 1.0
2 1 1 0.0 2.5 1.0 1.0

Bonds

1 1 1 2

Pair Coeffs

1 0.1 3.5

Bond Coeffs

1 300.0 1.5
"""

LAMMPS_DUMP = """ITEM: TIMESTEP
0
ITEM: NUMBER OF ATOMS
2
ITEM: BOX BOUNDS pp pp pp
0 20
0 20
0 20
ITEM: ATOMS id mol element x y z
1 1 C 1.0 1.0 1.0
2 1 C 2.5 1.0 1.0
"""


class ImportParserTests(unittest.TestCase):
    def test_import_settings_round_trip_with_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = ScymolProject(
                project_file=str(root / "scymol.json"),
                system_entry_mode="import",
                imported_structure_file="source.data",
                imported_trajectory_file="source.dump",
                molecules=[
                    MoleculeSpec(
                        name="ethane",
                        smiles="CC",
                        count=4,
                        formula="C2H6",
                        bond_order_status="inferred",
                    )
                ],
            )
            project.structure.source_mode = "imported"
            save_project(project)
            loaded = load_project(project.project_file)
            self.assertEqual(loaded.system_entry_mode, "import")
            self.assertEqual(loaded.structure.source_mode, "imported")
            self.assertEqual(loaded.molecules[0].formula, "C2H6")

    def test_reads_lammps_structure_and_trajectory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            structure_path = root / "structure.data"
            trajectory_path = root / "trajectory.lammpstrj"
            structure_path.write_text(LAMMPS_DATA, encoding="utf-8")
            trajectory_path.write_text(LAMMPS_DUMP, encoding="utf-8")
            structure = read_lammps_structure(structure_path)
            frame = read_first_lammps_frame(trajectory_path)
            self.assertEqual(len(structure.atoms), 2)
            self.assertEqual(len(structure.bonds), 1)
            self.assertEqual(structure.atoms[1].element, "C")
            self.assertEqual(structure.atom_style, "full")
            self.assertEqual(frame["columns"], ["id", "mol", "element", "x", "y", "z"])
            self.assertEqual(assess_direct_reuse(structure_path, structure), [])

    def test_missing_coefficients_require_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "structure.data"
            path.write_text(
                LAMMPS_DATA.replace("Pair Coeffs\n\n1 0.1 3.5\n\n", "").replace(
                    "Bond Coeffs\n\n1 300.0 1.5\n", ""
                ),
                encoding="utf-8",
            )
            structure = read_lammps_structure(path)
            issues = assess_direct_reuse(path, structure)
            self.assertTrue(any("Pair Coeffs" in issue for issue in issues))
            self.assertTrue(any("Bond Coeffs" in issue for issue in issues))

    def test_imported_structure_can_be_preserved_without_chemistry_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.data"
            source.write_text(LAMMPS_DATA, encoding="utf-8")
            project = ScymolProject(project_file=str(root / "scymol.json"))
            project.structure.source_mode = "imported"
            manifest_path = project.output_root / "system" / "system_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(
                json.dumps(
                    {
                        "entry_mode": "import",
                        "imported_structure_usable": True,
                        "imported_structure": str(source),
                        "molecules": [],
                    }
                ),
                encoding="utf-8",
            )
            result = build_structure(project)
            copied = Path(result["structure_data"])
            metadata = json.loads(Path(result["metadata"]).read_text(encoding="utf-8"))
            self.assertEqual(result["mode"], "imported")
            self.assertEqual(copied.read_text(encoding="utf-8"), LAMMPS_DATA)
            self.assertTrue(metadata["definition_signature"])
            self.assertTrue(metadata["build_signature"])

    def test_structure_import_copies_source_and_updates_project_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.data"
            source.write_text(LAMMPS_DATA, encoding="utf-8")
            project = ScymolProject(
                project_file=str(root / "project" / "scymol.json"),
                system_entry_mode="import",
                imported_structure_file=str(source),
            )
            species = [
                MoleculeSpec(
                    name="ethane",
                    smiles="CC",
                    count=1,
                    formula="C2H6",
                    bond_order_status="inferred",
                )
            ]

            def fake_artifacts(_detected, _molecule_dir, output_dir):
                system_pdb = output_dir / "system.pdb"
                system_pdb.write_text("PDB", encoding="utf-8")
                return species, [], system_pdb

            with patch(
                "scymol.system_import.detect_molecules",
                return_value=[DetectedMolecule([], object(), "CC", "C2H6", "inferred")],
            ), patch(
                "scymol.system_import.write_system_artifacts",
                side_effect=fake_artifacts,
            ):
                progress = []
                result = import_existing_system(project, progress=progress.append)

            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            copied_source = Path(manifest["imported_structure"])
            self.assertTrue(copied_source.is_file())
            self.assertNotEqual(copied_source, source)
            self.assertEqual(project.molecules[0].smiles, "CC")
            self.assertEqual(project.structure.source_mode, "imported")
            self.assertEqual(
                project.system_definition_signature,
                manifest["definition_signature"],
            )
            self.assertTrue(any("Parsed 2 atom(s) and 1 bond(s)" in line for line in progress))
            self.assertTrue(any("Detected 1 molecular species" in line for line in progress))


@unittest.skipUnless(HAS_QT, "PySide6 is not installed in this test runtime")
class ImportGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_system_page_exposes_two_clear_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            project = ScymolProject(project_file=str(Path(directory) / "scymol.json"))
            page = SystemPage()
            page.load_project(project)
            self.assertFalse(hasattr(page, "placement_box"))
            self.assertEqual(page.run_button.text(), "Validate and continue")
            self.assertTrue(page.composition_splitter.isVisibleTo(page))
            self.assertFalse(page.import_box.isVisibleTo(page))
            self.assertFalse(page.canvas.read_only)
            self.assertTrue(page.toolbar.isEnabled())
            self.assertEqual(len(page.canvas.connected_components()), 2)
            self.assertIn("×2", page.canvas.component_labels[0]["text"])
            page._add_species()
            self.assertEqual(len(project.molecules), 3)
            page.set_source_unconfigured()
            self.assertFalse(hasattr(page, "empty_source_box"))
            self.assertTrue(page.composition_splitter.isVisibleTo(page))
            page.set_source_mode("import")
            self.assertTrue(page.import_box.isVisibleTo(page))
            self.assertTrue(page.import_results_placeholder.isVisibleTo(page))
            self.assertFalse(page.composition_splitter.isVisibleTo(page))
            self.assertTrue(page.import_run_button.isVisibleTo(page))
            self.assertFalse(page.run_button.isVisibleTo(page))
            self.assertTrue(page.canvas.read_only)
            self.assertFalse(page.toolbar.isEnabled())

    def test_imported_species_remain_visible_without_invalidating_signature(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            species = MoleculeSpec(
                name="benzene",
                smiles="c1ccccc1",
                count=4,
                formula="C6H6",
                bond_order_status="inferred",
            )
            project = ScymolProject(
                project_file=str(root / "scymol.json"),
                system_entry_mode="import",
                imported_structure_file=str(root / "source.data"),
                molecules=[species],
            )
            signature = system_definition_signature(project)
            project.system_definition_signature = signature
            output = project.output_root / "system"
            output.mkdir(parents=True)
            (output / "system.pdb").write_text("PDB", encoding="utf-8")
            (output / "system_manifest.json").write_text(
                json.dumps(
                    {
                        "entry_mode": "import",
                        "definition_signature": signature,
                        "species": [
                            {
                                "id": species.id,
                                "name": species.name,
                                "smiles": species.smiles,
                                "formula": species.formula,
                                "count": species.count,
                                "bond_order_status": species.bond_order_status,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            page = SystemPage()
            page.load_project(project)

            self.assertEqual(project.system_definition_signature, signature)
            self.assertEqual(project.molecules[0].smiles, "c1ccccc1")
            self.assertTrue(page.composition_splitter.isVisibleTo(page))
            self.assertFalse(page.import_results_placeholder.isVisibleTo(page))
            self.assertEqual(len(page.canvas.connected_components()), 1)

    def test_structure_page_defaults_to_available_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = ScymolProject(project_file=str(root / "scymol.json"))
            project.structure.source_mode = "imported"
            source = root / "source.data"
            source.write_text(LAMMPS_DATA, encoding="utf-8")
            manifest = project.output_root / "system" / "system_manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "imported_structure_usable": True,
                        "imported_structure": str(source),
                    }
                ),
                encoding="utf-8",
            )
            page = StructurePage()
            page.load_project(project)
            self.assertTrue(hasattr(page, "placement_box"))
            self.assertTrue(page.imported_source.isChecked())
            self.assertFalse(page.placement_box.isEnabled())
            self.assertFalse(page.parameter_box.isEnabled())
            self.assertEqual(page.run_button.text(), "Use imported structure")


if __name__ == "__main__":
    unittest.main()
