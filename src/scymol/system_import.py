from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import json
import math
from pathlib import Path
import shutil
from typing import Callable

from .models import MoleculeSpec, ScymolProject, system_definition_signature


MASS_TO_ELEMENT = {
    "H": 1.008,
    "B": 10.81,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "Na": 22.990,
    "Mg": 24.305,
    "Al": 26.982,
    "Si": 28.085,
    "P": 30.974,
    "S": 32.06,
    "Cl": 35.45,
    "K": 39.098,
    "Ca": 40.078,
    "Br": 79.904,
    "I": 126.904,
}

SECTION_NAMES = {
    "Masses",
    "Atoms",
    "Bonds",
    "Angles",
    "Dihedrals",
    "Impropers",
    "Velocities",
    "Pair Coeffs",
    "PairIJ Coeffs",
    "Bond Coeffs",
    "Angle Coeffs",
    "Dihedral Coeffs",
    "Improper Coeffs",
}


@dataclass(frozen=True)
class ImportedAtom:
    atom_id: int
    molecule_id: int | None
    type_id: int
    charge: float
    element: str
    position: tuple[float, float, float]
    image: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class ImportedBond:
    bond_id: int
    type_id: int
    first: int
    second: int


@dataclass
class ImportedTopology:
    atoms: dict[int, ImportedAtom]
    bonds: list[ImportedBond]
    box: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    source_kind: str
    atom_style: str = "full"


@dataclass
class DetectedMolecule:
    atom_ids: list[int]
    mol: object
    smiles: str
    formula: str
    bond_order_status: str


def lammps_box_payload(
    box: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
) -> dict[str, float]:
    """Return imported LAMMPS bounds in the format used by Stage 2."""
    return {
        f"{axis}lo": float(bounds[0])
        for axis, bounds in zip("xyz", box)
    } | {
        f"{axis}hi": float(bounds[1])
        for axis, bounds in zip("xyz", box)
    }


def _report(progress: Callable[[str], None] | None, message: str):
    if progress is not None:
        progress(message)


def import_existing_system(
    project: ScymolProject, progress: Callable[[str], None] | None = None
) -> dict:
    """Import a LAMMPS data file and/or dump into Scymol's Stage 1 artifacts."""
    _report(progress, "Validating the selected structure and trajectory files.")
    structure_path = _existing_file(project.imported_structure_file)
    trajectory_path = _existing_file(project.imported_trajectory_file)
    if structure_path is None and trajectory_path is None:
        raise ValueError("Select a LAMMPS structure, a trajectory, or both.")

    output_dir = project.output_root / "system"
    molecule_dir = output_dir / "molecule_pdbs"
    imported_dir = output_dir / "imported"
    output_dir.mkdir(parents=True, exist_ok=True)
    if molecule_dir.exists():
        shutil.rmtree(molecule_dir)
    molecule_dir.mkdir(parents=True)
    imported_dir.mkdir(parents=True, exist_ok=True)

    copied_structure = None
    copied_trajectory = None
    last_trajectory_frame = None
    imported_structure_origin = ""
    warnings: list[str] = []
    if structure_path is not None:
        _report(progress, f"Copying and parsing LAMMPS structure: {structure_path}")
        copied_structure = imported_dir / "source_structure.data"
        if structure_path != copied_structure.resolve():
            shutil.copy2(structure_path, copied_structure)
        topology = read_lammps_structure(copied_structure)
        topology_source = "LAMMPS structure"
        imported_structure_origin = "lammps_data"
        direct_reuse_issues = assess_direct_reuse(copied_structure, topology)
        imported_forcefield_complete = not direct_reuse_issues
        imported_structure_usable = True
        warnings.extend(direct_reuse_issues)
        _report(
            progress,
            f"Parsed {len(topology.atoms)} atom(s) and {len(topology.bonds)} bond(s).",
        )
    else:
        _report(progress, f"Reading the last trajectory frame: {trajectory_path}")
        copied_trajectory = imported_dir / "source_trajectory.lammpstrj"
        if trajectory_path != copied_trajectory.resolve():
            shutil.copy2(trajectory_path, copied_trajectory)
        topology, inference = infer_topology_from_trajectory(
            copied_trajectory, use_last_frame=True
        )
        last_trajectory_frame = inference["frame"]
        copied_structure = imported_dir / "trajectory_snapshot.data"
        write_inferred_structure(topology, copied_structure)
        topology_source = "last trajectory frame with inferred connectivity"
        imported_structure_origin = "trajectory_snapshot"
        imported_structure_usable = True
        imported_forcefield_complete = False
        direct_reuse_issues = [
            "The trajectory snapshot contains coordinates, atom types, charges, and inferred "
            "bonds, but no force-field coefficients. Stage 2 must parameterize it; the "
            "last-frame positions and box will be preserved."
        ]
        warnings.extend(inference["warnings"])
        warnings.extend(direct_reuse_issues)
        _report(
            progress,
            f"Inferred {len(topology.atoms)} atom(s) and {len(topology.bonds)} bond(s) "
            f"from the last trajectory frame at timestep {inference['timestep']}.",
        )

    trajectory_summary = {}
    if trajectory_path is not None:
        if copied_trajectory is None:
            copied_trajectory = imported_dir / "source_trajectory.lammpstrj"
            if trajectory_path != copied_trajectory.resolve():
                shutil.copy2(trajectory_path, copied_trajectory)
        frame = last_trajectory_frame or read_last_lammps_frame(copied_trajectory)
        first_frame = read_first_lammps_frame(copied_trajectory)
        _report(
            progress,
            f"Validated last trajectory frame at timestep {frame['timestep']} "
            f"with {len(frame['rows'])} atom(s).",
        )
        frame_ids = {int(row["id"]) for row in frame["rows"]} if "id" in frame["columns"] else set()
        structure_ids = set(topology.atoms)
        aligned = frame_ids == structure_ids
        if structure_path is not None and not aligned:
            raise ValueError(
                "Trajectory atom IDs do not match the imported structure atom IDs."
            )
        if structure_path is not None:
            topology = topology_with_trajectory_frame(topology, frame)
            snapshot = imported_dir / "source_structure_last_frame.data"
            write_structure_frame_snapshot(
                copied_structure, frame, snapshot, topology.atom_style
            )
            copied_structure = snapshot
            imported_structure_origin = "structure_with_trajectory_snapshot"
            topology_source = "LAMMPS structure topology with last trajectory coordinates"
        trajectory_summary = {
            "atoms": len(frame["rows"]),
            "columns": frame["columns"],
            "first_timestep": first_frame["timestep"],
            "starting_timestep": frame["timestep"],
            "starting_frame": "last",
            "topology_aligned": aligned,
        }

    _report(progress, "Detecting connected molecules and assigning SMILES.")
    detected = detect_molecules(topology)
    if not detected:
        raise ValueError("No molecular species could be detected from the selected inputs.")
    species, manifest_instances, system_pdb = write_system_artifacts(
        detected, molecule_dir, output_dir
    )
    _report(
        progress,
        f"Detected {len(species)} molecular species across {len(detected)} molecule(s).",
    )
    project.molecules = species
    project.structure.atom_style = topology.atom_style
    for node in project.protocol.nodes:
        if node.kind == "Initialization":
            node.parameters["atom_style"] = topology.atom_style
    if imported_forcefield_complete:
        project.structure.source_mode = "imported"
    else:
        project.structure.source_mode = "parameterize"

    manifest_path = output_dir / "system_manifest.json"
    definition_signature = system_definition_signature(project)
    project.system_definition_signature = definition_signature
    manifest = {
        "entry_mode": "import",
        "definition_signature": definition_signature,
        "topology_source": topology_source,
        "atom_style": topology.atom_style,
        "box": lammps_box_payload(topology.box),
        "has_structure_input": structure_path is not None,
        "has_trajectory_input": trajectory_path is not None,
        "imported_structure_usable": imported_structure_usable,
        "imported_forcefield_complete": imported_forcefield_complete,
        "imported_structure_origin": imported_structure_origin,
        "direct_reuse_issues": direct_reuse_issues,
        "imported_structure": str(copied_structure.resolve()) if copied_structure else "",
        "imported_trajectory": str(copied_trajectory.resolve()) if copied_trajectory else "",
        "trajectory": trajectory_summary,
        "warnings": warnings,
        "species": [
            {
                "id": item.id,
                "name": item.name,
                "smiles": item.smiles,
                "formula": item.formula,
                "count": item.count,
                "bond_order_status": item.bond_order_status,
            }
            for item in species
        ],
        "molecules": manifest_instances,
        "files": {
            "system_pdb": str(system_pdb.resolve()),
            "manifest": str(manifest_path.resolve()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for warning in warnings:
        _report(progress, f"Warning: {warning}")
    _report(progress, f"Imported system artifacts written to {output_dir}.")
    return {
        "molecule_count": sum(item.count for item in species),
        "species_count": len(species),
        "system_pdb": str(system_pdb),
        "manifest": str(manifest_path),
        "warnings": warnings,
        "imported_structure_usable": imported_structure_usable,
    }


def merge_existing_systems(
    project: ScymolProject, progress: Callable[[str], None] | None = None
) -> dict:
    """Merge LAMMPS data geometries/topologies and prepare one clean typing pass.

    Source force-field types, charges, coefficients, and velocities are intentionally
    discarded. Coordinates and bonded connectivity are the only authoritative input.
    """
    sources = [source for source in project.merge_sources if source.path.strip()]
    if len(sources) < 2:
        raise ValueError("Select at least two LAMMPS data files to merge.")

    output_dir = project.output_root / "system"
    molecule_dir = output_dir / "molecule_pdbs"
    imported_dir = output_dir / "imported"
    source_dir = imported_dir / "merge_sources"
    output_dir.mkdir(parents=True, exist_ok=True)
    if molecule_dir.exists():
        shutil.rmtree(molecule_dir)
    if source_dir.exists():
        shutil.rmtree(source_dir)
    molecule_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)

    parsed_sources = []
    all_atoms: dict[int, ImportedAtom] = {}
    all_bonds: list[ImportedBond] = []
    atom_offset = 0
    molecule_offset = 0
    element_types: dict[str, int] = {}
    bounds = [[math.inf, -math.inf] for _ in range(3)]

    for source_index, source in enumerate(sources, start=1):
        path = _existing_file(source.path)
        if path is None:
            raise ValueError(f"Merge source {source_index} has no file.")
        copied = source_dir / f"{source_index:03d}_{path.name}"
        if path != copied.resolve():
            shutil.copy2(path, copied)
        _report(progress, f"Parsing merge source {source_index}/{len(sources)}: {path}")
        source_lines = copied.read_text(encoding="utf-8", errors="replace").splitlines()
        if any(
            raw.split("#", 1)[0].split()[-3:] == ["xy", "xz", "yz"]
            for raw in source_lines
        ):
            raise ValueError(
                f"Merge source {source_index} uses a triclinic/tilted box. "
                "The reliable merger currently accepts orthogonal LAMMPS boxes only."
            )
        topology = read_lammps_structure(copied)
        if any(high <= low for low, high in topology.box):
            raise ValueError(
                f"Merge source {source_index} has missing or invalid box bounds."
            )
        shift = (float(source.shift_x), float(source.shift_y), float(source.shift_z))
        component_map = _component_ids(
            sorted(topology.atoms),
            {(bond.first, bond.second) for bond in topology.bonds},
        )
        grouped_components: dict[int, list[int]] = defaultdict(list)
        for atom_id, component_id in component_map.items():
            grouped_components[component_id].append(atom_id)
        components = [
            sorted(grouped_components[key]) for key in sorted(grouped_components)
        ]
        component_ids = {
            atom_id: molecule_offset + component_index
            for component_index, component in enumerate(components, start=1)
            for atom_id in component
        }
        id_map = {old_id: atom_offset + old_id for old_id in topology.atoms}
        for old_id in sorted(topology.atoms):
            atom = topology.atoms[old_id]
            position = tuple(
                coordinate + delta
                for coordinate, delta in zip(
                    _unwrapped_position(atom, topology.box, (0, 0, 0)), shift
                )
            )
            for axis, coordinate in enumerate(position):
                bounds[axis][0] = min(bounds[axis][0], coordinate)
                bounds[axis][1] = max(bounds[axis][1], coordinate)
            type_id = element_types.setdefault(atom.element, len(element_types) + 1)
            new_id = id_map[old_id]
            all_atoms[new_id] = ImportedAtom(
                atom_id=new_id,
                molecule_id=component_ids[old_id],
                type_id=type_id,
                charge=0.0,
                element=atom.element,
                position=position,
                image=(0, 0, 0),
            )
        for bond in topology.bonds:
            all_bonds.append(
                ImportedBond(
                    bond_id=len(all_bonds) + 1,
                    type_id=1,
                    first=id_map[bond.first],
                    second=id_map[bond.second],
                )
            )
        for axis, ((low, high), delta) in enumerate(zip(topology.box, shift)):
            bounds[axis][0] = min(bounds[axis][0], low + delta)
            bounds[axis][1] = max(bounds[axis][1], high + delta)
        parsed_sources.append(
            {
                "source": str(path),
                "copied_source": str(copied.resolve()),
                "translation_angstrom": list(shift),
                "atoms": len(topology.atoms),
                "bonds": len(topology.bonds),
                "molecules": len(components),
                "box": lammps_box_payload(topology.box),
            }
        )
        atom_offset += len(topology.atoms)
        molecule_offset += len(components)

    # Keep every coordinate strictly inside the new orthogonal box so Stage 2's
    # periodic wrapping cannot move an atom sitting exactly on an upper bound.
    margin = 1.0e-6
    merged_box = tuple(
        (float(low) - margin, float(high) + margin) for low, high in bounds
    )
    merged = ImportedTopology(all_atoms, all_bonds, merged_box, "merged-lammps-data", "full")
    snapshot = imported_dir / "merged_topology.data"
    write_inferred_structure(merged, snapshot)
    _report(
        progress,
        f"Merged {len(all_atoms)} atom(s), {len(all_bonds)} bond(s), and "
        f"{molecule_offset} connected component(s).",
    )
    _report(progress, "Detecting species in the merged topology.")
    detected = detect_molecules(merged)
    if not detected:
        raise ValueError("No molecular species could be detected in the merged topology.")
    species, manifest_instances, system_pdb = write_system_artifacts(
        detected, molecule_dir, output_dir
    )
    project.molecules = species
    project.structure.source_mode = "parameterize"
    project.structure.atom_style = "full"
    for node in project.protocol.nodes:
        if node.kind == "Initialization":
            node.parameters["atom_style"] = "full"

    warning = (
        "Scymol did not resolve overlaps, reconcile periodic images, or validate the physical "
        "interface. Review the merged geometry before running LAMMPS."
    )
    direct_reuse_issues = [
        "Source force-field types, charges, coefficients, velocities, angles, dihedrals, and "
        "impropers were discarded. Stage 2 must reparameterize the complete merged topology."
    ]
    manifest_path = output_dir / "system_manifest.json"
    definition_signature = system_definition_signature(project)
    project.system_definition_signature = definition_signature
    manifest = {
        "entry_mode": "merge",
        "definition_signature": definition_signature,
        "topology_source": "Merged LAMMPS data geometries and bonded connectivity",
        "atom_style": "full",
        "box": lammps_box_payload(merged.box),
        "has_structure_input": True,
        "has_trajectory_input": False,
        "imported_structure_usable": True,
        "imported_forcefield_complete": False,
        "imported_structure_origin": "merged_topology",
        "direct_reuse_issues": direct_reuse_issues,
        "imported_structure": str(snapshot.resolve()),
        "imported_trajectory": "",
        "merge_sources": parsed_sources,
        "warnings": [warning, *direct_reuse_issues],
        "species": [
            {
                "id": item.id,
                "name": item.name,
                "smiles": item.smiles,
                "formula": item.formula,
                "count": item.count,
                "bond_order_status": item.bond_order_status,
            }
            for item in species
        ],
        "molecules": manifest_instances,
        "files": {
            "system_pdb": str(system_pdb.resolve()),
            "manifest": str(manifest_path.resolve()),
            "merged_topology": str(snapshot.resolve()),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for message in manifest["warnings"]:
        _report(progress, f"Warning: {message}")
    return {
        "molecule_count": len(detected),
        "species_count": len(species),
        "system_pdb": str(system_pdb),
        "manifest": str(manifest_path),
        "warnings": manifest["warnings"],
        "imported_structure_usable": True,
    }


def read_lammps_structure(path: str | Path) -> ImportedTopology:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"LAMMPS structure file does not exist: {source}")
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    sections, styles = _split_sections(lines)
    masses = _parse_masses(sections.get("Masses", []))
    atoms = _parse_atoms(sections.get("Atoms", []), styles.get("Atoms", ""), masses)
    if not atoms:
        raise ValueError(f"No atoms were found in the Atoms section of {source}.")
    bonds = _parse_bonds(sections.get("Bonds", []), atoms)
    expected_atoms = _header_count(lines, "atoms")
    expected_bonds = _header_count(lines, "bonds")
    if expected_atoms is not None and expected_atoms != len(atoms):
        raise ValueError(f"LAMMPS header declares {expected_atoms} atoms, parsed {len(atoms)}.")
    if expected_bonds is not None and expected_bonds != len(bonds):
        raise ValueError(f"LAMMPS header declares {expected_bonds} bonds, parsed {len(bonds)}.")
    ordered_ids = sorted(atoms)
    if ordered_ids != list(range(1, len(atoms) + 1)):
        raise ValueError("Imported systems currently require contiguous atom IDs starting at 1.")
    atom_style = styles.get("Atoms", "").split()[0] if styles.get("Atoms") else "full"
    return ImportedTopology(atoms, bonds, _parse_box(lines), "lammps-data", atom_style)


def assess_direct_reuse(path: str | Path, topology: ImportedTopology) -> list[str]:
    """Return reasons an imported data file is incomplete for Scymol's generated protocol."""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    sections, _ = _split_sections(lines)
    issues = []
    if "Pair Coeffs" not in sections and "PairIJ Coeffs" not in sections:
        issues.append(
            "The imported structure has no Pair Coeffs or PairIJ Coeffs section; Stage 2 reparameterization is required."
        )
    if topology.bonds and "Bond Coeffs" not in sections:
        issues.append(
            "The imported structure has bonds but no Bond Coeffs section; Stage 2 reparameterization is required."
        )
    for noun, section in (
        ("angles", "Angle Coeffs"),
        ("dihedrals", "Dihedral Coeffs"),
        ("impropers", "Improper Coeffs"),
    ):
        if (_header_count(lines, noun) or 0) > 0 and section not in sections:
            issues.append(
                f"The imported structure has {noun} but no {section} section; Stage 2 reparameterization is required."
            )
    if not topology.bonds and len(topology.atoms) > 1 and not _all_single_atom_molecules(topology):
        issues.append(
            "The imported structure contains no bonds for its multi-atom molecules; Stage 2 reparameterization is required."
        )
    return issues


def _iter_lammps_frames(path: str | Path):
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"LAMMPS trajectory does not exist: {source}")
    with source.open(encoding="utf-8", errors="replace") as handle:
        while True:
            line = handle.readline()
            while line and not line.startswith("ITEM: TIMESTEP"):
                line = handle.readline()
            if not line:
                return
            timestep = int(float(handle.readline().strip()))
            if not handle.readline().startswith("ITEM: NUMBER OF ATOMS"):
                raise ValueError("Malformed trajectory: NUMBER OF ATOMS header is missing.")
            atom_count = int(handle.readline().strip())
            if not handle.readline().startswith("ITEM: BOX BOUNDS"):
                raise ValueError("Malformed trajectory: BOX BOUNDS header is missing.")
            bounds = []
            for _ in range(3):
                values = handle.readline().split()
                if len(values) < 2:
                    raise ValueError("Malformed trajectory box bounds.")
                bounds.append((float(values[0]), float(values[1])))
            header = handle.readline().strip()
            if not header.startswith("ITEM: ATOMS"):
                raise ValueError("Malformed trajectory: ATOMS header is missing.")
            columns = header.split()[2:]
            rows = []
            for _ in range(atom_count):
                values = handle.readline().split()
                if len(values) != len(columns):
                    raise ValueError("Malformed trajectory atom row.")
                rows.append(dict(zip(columns, values)))
            yield {
                "timestep": timestep,
                "bounds": tuple(bounds),
                "columns": columns,
                "rows": rows,
            }


def read_first_lammps_frame(path: str | Path) -> dict:
    frame = next(_iter_lammps_frames(path), None)
    if frame is None:
        raise ValueError(f"No LAMMPS frame was found in {Path(path)}.")
    return frame


def read_last_lammps_frame(path: str | Path) -> dict:
    last = None
    for last in _iter_lammps_frames(path):
        pass
    if last is None:
        raise ValueError(f"No LAMMPS frame was found in {Path(path)}.")
    return last


def infer_topology_from_trajectory(
    path: str | Path, *, use_last_frame: bool = False
) -> tuple[ImportedTopology, dict]:
    try:
        from rdkit import Chem
        from rdkit.Chem import rdDetermineBonds
    except ImportError as exc:
        raise RuntimeError("RDKit is required to infer bonds from a trajectory.") from exc

    frame = (
        read_last_lammps_frame(path)
        if use_last_frame
        else read_first_lammps_frame(path)
    )
    columns = set(frame["columns"])
    if "id" not in columns:
        raise ValueError("Trajectory-only import requires an 'id' column.")
    if not ({"element", "el", "mass"} & columns):
        raise ValueError("Trajectory-only import requires an element, el, or mass column.")
    atoms = [_trajectory_atom(row, frame["bounds"], columns) for row in frame["rows"]]
    atoms.sort(key=lambda atom: atom.atom_id)
    if [atom.atom_id for atom in atoms] != list(range(1, len(atoms) + 1)):
        raise ValueError("Trajectory-only import requires contiguous atom IDs starting at 1.")

    use_molecule_ids = all(atom.molecule_id is not None and atom.molecule_id > 0 for atom in atoms)
    grouped: dict[int, list[ImportedAtom]] = defaultdict(list)
    if use_molecule_ids:
        for atom in atoms:
            grouped[int(atom.molecule_id)].append(atom)
        groups = [grouped[key] for key in sorted(grouped)]
    else:
        groups = [atoms]

    inferred_pairs: set[tuple[int, int]] = set()
    for group in groups:
        editable = Chem.RWMol()
        for atom in group:
            editable.AddAtom(Chem.Atom(atom.element))
        mol = editable.GetMol()
        conformer = Chem.Conformer(len(group))
        reference_image = group[0].image
        for index, atom in enumerate(group):
            conformer.SetAtomPosition(
                index, _unwrapped_position(atom, frame["bounds"], reference_image)
            )
        mol.AddConformer(conformer)
        try:
            rdDetermineBonds.DetermineConnectivity(mol)
        except Exception as exc:
            raise ValueError(f"RDKit could not infer trajectory connectivity: {exc}") from exc
        if use_molecule_ids and len(group) > 1 and mol.GetNumBonds() == 0:
            raise ValueError(
                f"RDKit found no bonds for trajectory molecule {group[0].molecule_id}. "
                "Check wrapped coordinates, image flags, and element or mass columns."
            )
        for bond in mol.GetBonds():
            first = group[bond.GetBeginAtomIdx()].atom_id
            second = group[bond.GetEndAtomIdx()].atom_id
            inferred_pairs.add(tuple(sorted((first, second))))

    if use_molecule_ids:
        molecule_ids = {atom.atom_id: int(atom.molecule_id) for atom in atoms}
    else:
        molecule_ids = _component_ids([atom.atom_id for atom in atoms], inferred_pairs)
    normalized_atoms = {
        atom.atom_id: ImportedAtom(
            atom.atom_id,
            molecule_ids[atom.atom_id],
            atom.type_id,
            atom.charge,
            atom.element,
            atom.position,
            atom.image,
        )
        for atom in atoms
    }
    bonds = [
        ImportedBond(index, 1, first, second)
        for index, (first, second) in enumerate(sorted(inferred_pairs), start=1)
    ]
    warnings = [
        "Connectivity was inferred from the "
        + ("last" if use_last_frame else "first")
        + " trajectory frame and must be reviewed before use."
    ]
    if not use_molecule_ids:
        warnings.append(
            "The trajectory has no positive molecule IDs; molecule boundaries were inferred from distances."
        )
    return (
        ImportedTopology(normalized_atoms, bonds, frame["bounds"], "trajectory-inferred", "full"),
        {
            "warnings": warnings,
            "used_molecule_ids": use_molecule_ids,
            "timestep": frame["timestep"],
            "frame": frame,
        },
    )


def detect_molecules(topology: ImportedTopology) -> list[DetectedMolecule]:
    try:
        from rdkit import Chem
        from rdkit.Chem import rdDetermineBonds
    except ImportError as exc:
        raise RuntimeError("RDKit is required to identify molecular species.") from exc

    components = _components(topology)
    detected = []
    for atom_ids in components:
        reference_image = topology.atoms[atom_ids[0]].image
        local = {atom_id: index for index, atom_id in enumerate(atom_ids)}
        editable = Chem.RWMol()
        for atom_id in atom_ids:
            editable.AddAtom(Chem.Atom(topology.atoms[atom_id].element))
        for bond in topology.bonds:
            if bond.first in local and bond.second in local:
                editable.AddBond(local[bond.first], local[bond.second], Chem.BondType.SINGLE)
        mol = editable.GetMol()
        conformer = Chem.Conformer(len(atom_ids))
        for index, atom_id in enumerate(atom_ids):
            conformer.SetAtomPosition(
                index,
                _unwrapped_position(
                    topology.atoms[atom_id], topology.box, reference_image
                ),
            )
        mol.AddConformer(conformer)
        charge = round(sum(topology.atoms[atom_id].charge for atom_id in atom_ids))
        try:
            rdDetermineBonds.DetermineBondOrders(mol, charge=charge)
            Chem.SanitizeMol(mol)
            status = "inferred"
        except Exception:
            try:
                Chem.SanitizeMol(mol)
            except Exception:
                pass
            status = "connectivity-only"
        heavy = Chem.RemoveHs(mol, sanitize=False)
        try:
            Chem.SanitizeMol(heavy)
            smiles = Chem.MolToSmiles(heavy, canonical=True)
        except Exception:
            smiles = ""
        detected.append(
            DetectedMolecule(
                atom_ids=atom_ids,
                mol=mol,
                smiles=smiles,
                formula=_formula([topology.atoms[atom_id].element for atom_id in atom_ids]),
                bond_order_status=status,
            )
        )
    return detected


def write_system_artifacts(detected, molecule_dir: Path, output_dir: Path):
    from rdkit import Chem

    buckets: dict[tuple, list[DetectedMolecule]] = defaultdict(list)
    for molecule in detected:
        key = (molecule.smiles, molecule.formula, _graph_signature(molecule.mol))
        buckets[key].append(molecule)

    species: list[MoleculeSpec] = []
    species_by_key = {}
    for species_index, (key, group) in enumerate(buckets.items(), start=1):
        representative = group[0]
        spec = MoleculeSpec(
            name=f"species_{species_index}",
            smiles=representative.smiles,
            count=len(group),
            formula=representative.formula,
            bond_order_status=representative.bond_order_status,
        )
        species.append(spec)
        species_by_key[key] = spec

    instances = []
    combined = None
    copy_counts = defaultdict(int)
    for instance_index, molecule in enumerate(detected, start=1):
        key = (molecule.smiles, molecule.formula, _graph_signature(molecule.mol))
        spec = species_by_key[key]
        copy_counts[spec.id] += 1
        instance_name = f"{instance_index:04d}_{spec.name}_{copy_counts[spec.id]}"
        pdb_path = molecule_dir / f"{instance_name}.pdb"
        Chem.MolToPDBFile(molecule.mol, str(pdb_path))
        combined = molecule.mol if combined is None else Chem.CombineMols(combined, molecule.mol)
        instances.append(
            {
                "instance": instance_name,
                "species_id": spec.id,
                "name": spec.name,
                "smiles": spec.smiles,
                "formula": spec.formula,
                "pdb": str(pdb_path.resolve()),
                "source_atom_ids": molecule.atom_ids,
                "bond_order_status": molecule.bond_order_status,
                "viewer_bond_orders": [
                    {
                        "atoms": [
                            molecule.atom_ids[bond.GetBeginAtomIdx()],
                            molecule.atom_ids[bond.GetEndAtomIdx()],
                        ],
                        "order": (
                            "aromatic"
                            if bond.GetIsAromatic()
                            else float(bond.GetBondTypeAsDouble())
                        ),
                    }
                    for bond in molecule.mol.GetBonds()
                ],
            }
        )
    system_pdb = output_dir / "system.pdb"
    Chem.MolToPDBFile(combined, str(system_pdb))
    return species, instances, system_pdb


def write_inferred_structure(topology: ImportedTopology, path: str | Path) -> Path:
    target = Path(path)
    type_elements = {}
    for atom in topology.atoms.values():
        type_elements.setdefault(atom.type_id, atom.element)
    lines = [
        "LAMMPS structure inferred by Scymol from trajectory coordinates",
        "",
        f"{len(topology.atoms)} atoms",
        f"{len(topology.bonds)} bonds",
        "",
        f"{len(type_elements)} atom types",
        f"{1 if topology.bonds else 0} bond types",
        "",
    ]
    for axis, (low, high) in zip("xyz", topology.box):
        lines.append(f"{low:.12g} {high:.12g} {axis}lo {axis}hi")
    lines.extend(["", "Masses", ""])
    for type_id, element in sorted(type_elements.items()):
        lines.append(f"{type_id} {MASS_TO_ELEMENT[element]:.8g} # {element}")
    lines.extend(["", "Atoms # full", ""])
    for atom in topology.atoms.values():
        x, y, z = atom.position
        ix, iy, iz = atom.image
        lines.append(
            f"{atom.atom_id} {atom.molecule_id} {atom.type_id} {atom.charge:.12g} "
            f"{x:.12g} {y:.12g} {z:.12g} {ix} {iy} {iz} # {atom.element}"
        )
    if topology.bonds:
        lines.extend(["", "Bonds", ""])
        lines.extend(
            f"{bond.bond_id} {bond.type_id} {bond.first} {bond.second}"
            for bond in topology.bonds
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def topology_with_trajectory_frame(
    topology: ImportedTopology, frame: dict
) -> ImportedTopology:
    columns = set(frame["columns"])
    rows = {int(row["id"]): row for row in frame["rows"]}
    atoms = {}
    for atom_id, atom in topology.atoms.items():
        row = rows[atom_id]
        position, image = _trajectory_coordinates(row, frame["bounds"], columns)
        atoms[atom_id] = ImportedAtom(
            atom_id=atom.atom_id,
            molecule_id=atom.molecule_id,
            type_id=atom.type_id,
            charge=atom.charge,
            element=atom.element,
            position=position,
            image=image,
        )
    return ImportedTopology(
        atoms=atoms,
        bonds=topology.bonds,
        box=frame["bounds"],
        source_kind="structure-with-trajectory-snapshot",
        atom_style=topology.atom_style,
    )


def write_structure_frame_snapshot(
    source: str | Path,
    frame: dict,
    target: str | Path,
    atom_style: str,
) -> Path:
    """Copy a LAMMPS data file while replacing its box and atom coordinates."""
    rows = {int(row["id"]): row for row in frame["rows"]}
    columns = set(frame["columns"])
    coordinates = {
        atom_id: _trajectory_coordinates(row, frame["bounds"], columns)
        for atom_id, row in rows.items()
    }
    bounds = dict(zip("xyz", frame["bounds"]))
    output = []
    section = ""
    for raw in Path(source).read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        heading = stripped.split("#", 1)[0].strip()
        if heading in SECTION_NAMES:
            section = heading
            output.append(raw)
            continue
        header = stripped.split("#", 1)[0].split()
        if len(header) >= 4 and header[2:4] in (
            ["xlo", "xhi"],
            ["ylo", "yhi"],
            ["zlo", "zhi"],
        ):
            axis = header[2][0]
            low, high = bounds[axis]
            output.append(f"{low:.12g} {high:.12g} {axis}lo {axis}hi")
            continue
        if section != "Atoms":
            output.append(raw)
            continue
        data, separator, comment = raw.partition("#")
        values = data.split()
        if not values:
            output.append(raw)
            continue
        try:
            atom_id = int(values[0])
            position, image = coordinates[atom_id]
            start = _atom_coordinate_start(values, atom_style)
        except (KeyError, ValueError):
            output.append(raw)
            continue
        values[start : start + 3] = [f"{value:.12g}" for value in position]
        if len(values) >= start + 6:
            values[start + 3 : start + 6] = [str(value) for value in image]
        else:
            values.extend(str(value) for value in image)
        rebuilt = " ".join(values)
        if separator:
            rebuilt += f" # {comment.strip()}"
        output.append(rebuilt)
    destination = Path(target)
    destination.write_text("\n".join(output) + "\n", encoding="utf-8")
    return destination


def _atom_coordinate_start(values: list[str], style: str) -> int:
    normalized = style.lower().strip()
    if normalized == "full" or (not normalized and len(values) in {7, 10}):
        return 4
    if normalized == "charge":
        return 3
    if normalized in {"molecular", "bond", "angle"} or (
        not normalized and len(values) in {6, 9}
    ):
        return 3
    if normalized == "atomic" or (not normalized and len(values) in {5, 8}):
        return 2
    raise ValueError("Could not identify atom coordinates in the imported structure.")


def _existing_file(value: str) -> Path | None:
    if not value.strip():
        return None
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Selected input does not exist: {path}")
    return path


def _split_sections(lines):
    sections: dict[str, list[str]] = defaultdict(list)
    styles = {}
    current = None
    for raw in lines:
        text = raw.strip()
        heading = text.split("#", 1)[0].strip()
        if heading in SECTION_NAMES:
            current = heading
            styles[heading] = text.split("#", 1)[1].strip().lower() if "#" in text else ""
            continue
        if current is not None:
            sections[current].append(raw)
    return sections, styles


def _parse_masses(lines):
    result = {}
    for raw in lines:
        data, _, comment = raw.partition("#")
        values = data.split()
        if len(values) >= 2:
            result[int(values[0])] = (float(values[1]), _element_from_comment(comment))
    return result


def _parse_atoms(lines, style, masses):
    atoms = {}
    for raw in lines:
        data, _, comment = raw.partition("#")
        values = data.split()
        if not values:
            continue
        atom_id, molecule_id, type_id, charge, xyz, image = _decode_atom(values, style)
        element = _element_from_comment(comment)
        if element is None:
            if type_id not in masses:
                raise ValueError(f"Atom type {type_id} has no Masses entry or element comment.")
            mass, element = masses[type_id]
            element = element or _element_from_mass(mass)
        if atom_id in atoms:
            raise ValueError(f"Duplicate atom ID {atom_id}.")
        atoms[atom_id] = ImportedAtom(atom_id, molecule_id, type_id, charge, element, xyz, image)
    return atoms


def _decode_atom(values, style):
    style = style.split()[0] if style else ""
    if style in {"full", "charge"} or (not style and len(values) in {7, 10}):
        atom_id = int(values[0])
        if style == "charge":
            molecule_id, type_id, charge, start = None, int(values[1]), float(values[2]), 3
        else:
            molecule_id, type_id, charge, start = int(values[1]), int(values[2]), float(values[3]), 4
    elif style in {"molecular", "bond", "angle"} or (not style and len(values) in {6, 9}):
        atom_id, molecule_id, type_id, charge, start = int(values[0]), int(values[1]), int(values[2]), 0.0, 3
    elif style == "atomic" or (not style and len(values) in {5, 8}):
        atom_id, molecule_id, type_id, charge, start = int(values[0]), None, int(values[1]), 0.0, 2
    else:
        raise ValueError("Could not infer atom style; annotate the Atoms section with its style.")
    xyz = tuple(float(value) for value in values[start : start + 3])
    if len(xyz) != 3:
        raise ValueError(f"Malformed atom row: {' '.join(values)}")
    trailing = values[start + 3 : start + 6]
    image = tuple(int(value) for value in trailing) if len(trailing) == 3 else (0, 0, 0)
    return atom_id, molecule_id, type_id, charge, xyz, image


def _parse_bonds(lines, atoms):
    bonds = []
    for raw in lines:
        values = raw.split("#", 1)[0].split()
        if not values:
            continue
        if len(values) < 4:
            raise ValueError(f"Malformed bond row: {raw}")
        bond = ImportedBond(*(int(value) for value in values[:4]))
        if bond.first not in atoms or bond.second not in atoms:
            raise ValueError(f"Bond {bond.bond_id} references a missing atom.")
        bonds.append(bond)
    return bonds


def _parse_box(lines):
    values = {}
    for raw in lines:
        parts = raw.split("#", 1)[0].split()
        if len(parts) >= 4 and parts[2:4] in (["xlo", "xhi"], ["ylo", "yhi"], ["zlo", "zhi"]):
            values[parts[2][0]] = (float(parts[0]), float(parts[1]))
    return tuple(values.get(axis, (0.0, 0.0)) for axis in "xyz")


def _header_count(lines, noun):
    for raw in lines:
        values = raw.split("#", 1)[0].split()
        if len(values) == 2 and values[1].lower() == noun.lower():
            try:
                return int(values[0])
            except ValueError:
                return None
    return None


def _trajectory_atom(row, bounds, columns):
    element = row.get("element") or row.get("el")
    if element is None:
        element = _element_from_mass(float(row["mass"]))
    position, image = _trajectory_coordinates(row, bounds, columns)
    type_id = int(row.get("type", 0))
    if type_id <= 0:
        ordered = list(MASS_TO_ELEMENT)
        type_id = ordered.index(element) + 1
    return ImportedAtom(
        int(row["id"]),
        int(row["mol"]) if row.get("mol") else None,
        type_id,
        float(row.get("q", row.get("charge", 0.0))),
        element,
        position,
        image,
    )


def _trajectory_position(row, bounds, columns):
    """Return wrapped coordinates, matching the frame shown by the viewer."""
    return _trajectory_coordinates(row, bounds, columns)[0]


def _trajectory_coordinates(row, bounds, columns):
    """Return primary-box coordinates plus LAMMPS periodic image flags."""
    position = []
    images = []
    for axis, (low, high) in zip("xyz", bounds):
        length = high - low
        image_key = f"i{axis}"
        image = int(row.get(image_key, 0))
        if axis in columns:
            coordinate = float(row[axis])
        elif f"{axis}s" in columns:
            coordinate = low + float(row[f"{axis}s"]) * (high - low)
        elif f"{axis}u" in columns:
            unwrapped = float(row[f"{axis}u"])
            image = math.floor((unwrapped - low) / length)
            coordinate = unwrapped - image * length
        elif f"{axis}su" in columns:
            unwrapped_scaled = float(row[f"{axis}su"])
            image = math.floor(unwrapped_scaled)
            coordinate = low + (unwrapped_scaled - image) * length
        else:
            raise ValueError("Trajectory-only import requires x/y/z coordinates.")
        position.append(coordinate)
        images.append(image)
    return tuple(position), tuple(images)


def _components(topology):
    atom_ids = sorted(topology.atoms)
    molecule_ids = [topology.atoms[atom_id].molecule_id for atom_id in atom_ids]
    if molecule_ids and all(value is not None and value > 0 for value in molecule_ids):
        grouped = defaultdict(list)
        for atom_id in atom_ids:
            grouped[int(topology.atoms[atom_id].molecule_id)].append(atom_id)
        crossing = [
            bond
            for bond in topology.bonds
            if topology.atoms[bond.first].molecule_id
            != topology.atoms[bond.second].molecule_id
        ]
        if crossing:
            raise ValueError(
                f"Found {len(crossing)} bonds connecting different LAMMPS molecule IDs."
            )
        return [grouped[key] for key in sorted(grouped)]
    pairs = {(bond.first, bond.second) for bond in topology.bonds}
    component_map = _component_ids(atom_ids, pairs)
    grouped = defaultdict(list)
    for atom_id, component_id in component_map.items():
        grouped[component_id].append(atom_id)
    return [sorted(grouped[key]) for key in sorted(grouped)]


def _all_single_atom_molecules(topology):
    molecule_ids = [atom.molecule_id for atom in topology.atoms.values()]
    if not molecule_ids or not all(value is not None and value > 0 for value in molecule_ids):
        return len(topology.atoms) == 1
    return all(count == 1 for count in Counter(molecule_ids).values())


def _component_ids(atom_ids, bonds):
    adjacency = {atom_id: set() for atom_id in atom_ids}
    for first, second in bonds:
        adjacency[first].add(second)
        adjacency[second].add(first)
    remaining = set(atom_ids)
    result = {}
    component_id = 0
    while remaining:
        component_id += 1
        stack = [min(remaining)]
        found = set()
        while stack:
            atom_id = stack.pop()
            if atom_id in found:
                continue
            found.add(atom_id)
            stack.extend(adjacency[atom_id] - found)
        remaining -= found
        result.update({atom_id: component_id for atom_id in found})
    return result


def _graph_signature(mol):
    return tuple(
        sorted(
            (
                atom.GetSymbol(),
                atom.GetDegree(),
                tuple(sorted(neighbor.GetSymbol() for neighbor in atom.GetNeighbors())),
            )
            for atom in mol.GetAtoms()
        )
    )


def _formula(elements):
    counts = Counter(elements)
    order = (["C"] if "C" in counts else []) + (["H"] if "H" in counts else [])
    order += sorted(element for element in counts if element not in {"C", "H"})
    return "".join(element + (str(counts[element]) if counts[element] != 1 else "") for element in order)


def _element_from_comment(comment):
    for token in comment.replace("_", " ").replace("-", " ").split():
        normalized = token[:1].upper() + token[1:].lower()
        if normalized in MASS_TO_ELEMENT:
            return normalized
    return None


def _element_from_mass(mass):
    element, reference = min(MASS_TO_ELEMENT.items(), key=lambda item: abs(item[1] - mass))
    if abs(reference - mass) > 0.75:
        raise ValueError(f"Could not infer an element from mass {mass}.")
    return element


def _unwrapped_position(atom, box, reference_image=(0, 0, 0)):
    return tuple(
        coordinate + (image - origin) * (high - low)
        for coordinate, image, origin, (low, high) in zip(
            atom.position, atom.image, reference_image, box
        )
    )
