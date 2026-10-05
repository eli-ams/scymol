from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scymol.chemistry import (
    _copy_typed_system_with_positions,
    _pushd,
    _random_rotation_matrix,
    _run_pysimm_and_promote_input,
    _set_box,
    _sobol_points_3d,
    validate_system_definition,
)
from scymol.models import (
    MoleculeSpec,
    ProtocolEdge,
    ProtocolNode,
    ScymolProject,
    structure_build_signature,
    system_definition_signature,
)
from scymol.project_io import load_project, save_project
from scymol.protocol import (
    default_protocol,
    protocol_paths,
    tutorial_protocol,
    validate_graph,
)
from scymol.schemas import default_parameters
from scymol.run_generation import generate_run

try:
    import rdkit  # noqa: F401

    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


class ProtocolTests(unittest.TestCase):
    def test_new_project_starts_at_thirty_percent_packing_density(self):
        self.assertEqual(ScymolProject().system_initial_density_fraction, 0.30)
        self.assertEqual(
            ScymolProject.from_dict({}).system_initial_density_fraction,
            0.30,
        )

    def test_unsaved_project_has_no_fallback_workspace(self):
        with self.assertRaisesRegex(RuntimeError, "Create or open a project"):
            _ = ScymolProject().root

    def test_default_protocol_is_one_valid_path(self):
        graph = default_protocol()
        self.assertEqual(validate_graph(graph), [])
        self.assertEqual(len(protocol_paths(graph)), 1)
        self.assertEqual(
            [node.kind for node in protocol_paths(graph)[0]],
            ["Initialization", "Minimization", "Velocities", "NVT"],
        )

    def test_branch_creates_two_paths(self):
        graph = default_protocol()
        branch = ProtocolNode(kind="NVE", name="NVE branch", parameters=default_parameters("NVE"))
        graph.nodes.append(branch)
        graph.edges.append(ProtocolEdge(graph.nodes[2].id, branch.id))
        self.assertEqual(len(protocol_paths(graph)), 2)

    def test_tutorial_protocol_is_fixed_at_room_temperature(self):
        graph = tutorial_protocol()
        self.assertEqual(validate_graph(graph), [])
        self.assertEqual(
            [node.kind for node in graph.nodes],
            ["Initialization", "Minimization", "Velocities", "NVT"],
        )
        for node in graph.nodes:
            for parameter in ("temperature", "temperature_start", "temperature_end"):
                if parameter in node.parameters:
                    self.assertEqual(node.parameters[parameter], 298.15)


class RunGenerationTests(unittest.TestCase):
    def test_project_round_trip_and_generation(self):
        project = ScymolProject(protocol=default_protocol())
        project.system_target_density_kg_m3 = 875.0
        project.system_initial_density_fraction = 0.025
        project.system_rotate_molecules = False
        project.system_definition_signature = system_definition_signature(project)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project.project_file = str(root / "scymol.json")
            save_project(project)
            loaded = load_project(project.project_file)
            self.assertEqual(loaded.system_target_density_kg_m3, 875.0)
            self.assertEqual(loaded.system_initial_density_fraction, 0.025)
            self.assertFalse(loaded.system_rotate_molecules)
            self.assertEqual(
                loaded.system_definition_signature,
                project.system_definition_signature,
            )
            structure = root / "output" / "structure" / "structure.data"
            structure.parent.mkdir(parents=True)
            structure.write_text("LAMMPS structure", encoding="utf-8")
            progress = []
            record = generate_run(
                loaded,
                root / "simulations",
                sequence=1,
                progress=progress.append,
            )
            self.assertRegex(record.name, r"^1_\d{8}_\d{6}$")
            simulation_dir = Path(record.output_dir)
            self.assertTrue(Path(record.scripts[0]).exists())
            self.assertTrue((simulation_dir / "run_manifest.json").exists())
            self.assertEqual(
                (simulation_dir / "structure.data").read_text(encoding="utf-8"),
                "LAMMPS structure",
            )
            self.assertTrue(any("current protocol" in line for line in progress))

    def test_legacy_campaign_fields_are_ignored_when_loading(self):
        payload = ScymolProject(protocol=default_protocol()).to_dict()
        payload["campaign_mode"] = "zip"
        payload["campaign_variables"] = [{"target": "legacy", "values": [1, 2]}]
        payload["runs"] = [{"name": "old run", "variables": {"legacy": 1}}]
        project = ScymolProject.from_dict(payload)
        self.assertFalse(hasattr(project, "campaign_variables"))
        self.assertEqual(project.runs[0].name, "old run")


class PySimmCompatibilityTests(unittest.TestCase):
    def test_typed_species_copy_receives_instance_coordinates(self):
        class Particle:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        class FakeSystem:
            def __init__(self, coordinates):
                self.particles = [Particle(*position) for position in coordinates]

            def copy(self):
                return FakeSystem(
                    [(item.x, item.y, item.z) for item in self.particles]
                )

        parent = FakeSystem([(0, 0, 0), (1, 0, 0)])
        copied = _copy_typed_system_with_positions(
            parent, [(4, 5, 6), (7, 8, 9)], "ethane"
        )

        self.assertEqual(
            [(item.x, item.y, item.z) for item in copied.particles],
            [(4.0, 5.0, 6.0), (7.0, 8.0, 9.0)],
        )
        self.assertEqual(
            [(item.x, item.y, item.z) for item in parent.particles],
            [(0, 0, 0), (1, 0, 0)],
        )

    def test_typed_species_copy_rejects_atom_count_mismatch(self):
        class FakeSystem:
            particles = [object()]

            def copy(self):
                return self

        with self.assertRaisesRegex(ValueError, "1 atoms.*2 coordinates"):
            _copy_typed_system_with_positions(
                FakeSystem(), [(0, 0, 0), (1, 1, 1)], "bad copy"
            )

    def test_post_write_type_error_is_treated_as_warning(self):
        class FakeSimulation:
            def run(self, save_input=False):
                self.assert_save_input = save_input
                Path("temp.lmps").write_text("LAMMPS data", encoding="utf-8")
                raise TypeError("expected str, bytes or os.PathLike object, not NoneType")

        with tempfile.TemporaryDirectory() as directory, _pushd(Path(directory)):
            progress = []
            warning = _run_pysimm_and_promote_input(
                FakeSimulation(), progress=progress.append
            )
            self.assertIn("NoneType", warning)
            self.assertFalse(Path("temp.lmps").exists())
            self.assertEqual(Path("structure.data").read_text(encoding="utf-8"), "LAMMPS data")
            self.assertTrue(any(line.startswith("Warning:") for line in progress))

    def test_type_error_is_fatal_when_temp_input_is_missing(self):
        class FakeSimulation:
            def run(self, save_input=False):
                raise TypeError("known warning, but no file")

        with tempfile.TemporaryDirectory() as directory, _pushd(Path(directory)):
            with self.assertRaisesRegex(RuntimeError, "did not write temp.lmps"):
                _run_pysimm_and_promote_input(FakeSimulation())


class PackingTests(unittest.TestCase):
    def test_sobol_points_are_reproducible_unique_and_bounded(self):
        import numpy as np

        first = _sobol_points_3d(128, skip=37)
        second = _sobol_points_3d(128, skip=37)
        self.assertTrue(np.array_equal(first, second))
        self.assertEqual(len(np.unique(first, axis=0)), 128)
        self.assertTrue(np.all(first >= 0.0))
        self.assertTrue(np.all(first < 1.0))

    def test_seeded_rotation_is_orthonormal(self):
        import numpy as np

        rotation = _random_rotation_matrix(np.random.default_rng(1234))
        self.assertTrue(np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-12))
        self.assertAlmostEqual(float(np.linalg.det(rotation)), 1.0, places=12)

    def test_packing_box_is_preserved_for_pysimm(self):
        class Dimensions:
            pass

        class FakeSystem:
            dim = Dimensions()

        box = {
            "xlo": -10,
            "xhi": 10,
            "ylo": -11,
            "yhi": 11,
            "zlo": -12,
            "zhi": 12,
        }
        system = FakeSystem()
        _set_box(system, [(0, 0, 0)], padding=8, placement_box=box)
        self.assertEqual((system.dim.xlo, system.dim.xhi), (-10.0, 10.0))
        self.assertEqual((system.dim.ylo, system.dim.yhi), (-11.0, 11.0))
        self.assertEqual((system.dim.zlo, system.dim.zhi), (-12.0, 12.0))


@unittest.skipUnless(HAS_RDKIT, "RDKit is not installed in this test runtime")
class SystemDefinitionTests(unittest.TestCase):
    def test_validation_does_not_generate_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            project = ScymolProject(
                project_file=str(Path(directory) / "scymol.json"),
                molecules=[MoleculeSpec(name="ethanol", smiles="CCO", count=3)],
            )
            result = validate_system_definition(project)
            self.assertEqual(result["species_count"], 1)
            self.assertEqual(result["molecule_count"], 3)
            self.assertEqual(result["signature"], system_definition_signature(project))
            self.assertFalse(project.output_root.exists())

    def test_validation_rejects_disconnected_species(self):
        project = ScymolProject(
            molecules=[MoleculeSpec(name="mixture", smiles="CC.O", count=1)]
        )
        with self.assertRaisesRegex(ValueError, "disconnected fragments"):
            validate_system_definition(project)


class ArtifactSignatureTests(unittest.TestCase):
    def test_stage_two_settings_do_not_invalidate_stage_one(self):
        project = ScymolProject()
        definition_before = system_definition_signature(project)
        structure_before = structure_build_signature(project)
        project.system_target_density_kg_m3 = 875.0
        self.assertEqual(system_definition_signature(project), definition_before)
        self.assertNotEqual(structure_build_signature(project), structure_before)

    def test_composition_changes_invalidate_both_stages(self):
        project = ScymolProject()
        definition_before = system_definition_signature(project)
        structure_before = structure_build_signature(project)
        project.molecules[0].count += 1
        self.assertNotEqual(system_definition_signature(project), definition_before)
        self.assertNotEqual(structure_build_signature(project), structure_before)


if __name__ == "__main__":
    unittest.main()
