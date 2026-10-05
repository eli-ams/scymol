from __future__ import annotations

from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import shutil
from typing import Callable

import numpy as np

from .models import (
    ScymolProject,
    structure_build_signature,
    system_definition_signature,
)
from .system_import import (
    import_existing_system,
    lammps_box_payload,
    merge_existing_systems,
    read_lammps_structure,
)


ProgressCallback = Callable[[str], None]


def _report(progress: ProgressCallback | None, message: str):
    if progress is not None:
        progress(message)


def clear_structure_artifacts(project: ScymolProject):
    """Remove Stage 2 products after Stage 1 has produced a new system."""
    output_dir = project.output_root / "structure"
    if output_dir.exists():
        shutil.rmtree(output_dir)


def validate_system_definition(
    project: ScymolProject, progress: ProgressCallback | None = None
) -> dict:
    """Validate Stage 1 without generating conformers or packed coordinates."""
    if project.system_entry_mode != "build":
        raise ValueError("Existing systems must be analyzed with Analyze and import.")
    if not project.molecules:
        raise ValueError("Add at least one molecular species.")
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError("RDKit is required to validate molecular definitions.") from exc

    _report(progress, "Validating molecular identities, connectivity, and counts.")
    total = 0
    for index, molecule in enumerate(project.molecules, start=1):
        name = molecule.name.strip() or f"Molecule {index}"
        smiles = molecule.smiles.strip()
        if not smiles:
            raise ValueError(f"{name} has no SMILES definition.")
        parsed = Chem.MolFromSmiles(smiles)
        if parsed is None:
            raise ValueError(f"RDKit could not parse SMILES for {name!r}: {smiles}")
        if len(Chem.GetMolFrags(parsed)) != 1:
            raise ValueError(
                f"{name} contains disconnected fragments. Add each species separately."
            )
        if molecule.count < 1:
            raise ValueError(f"{name} must have a count of at least one.")
        total += int(molecule.count)
        _report(progress, f"Validated {name}: {smiles} × {molecule.count}.")

    return {
        "species_count": len(project.molecules),
        "molecule_count": total,
        "signature": system_definition_signature(project),
    }


def build_system(
    project: ScymolProject,
    progress: ProgressCallback | None = None,
    *,
    rebuild_imported: bool = False,
) -> dict:
    """Generate conformers and pack the Stage 1 definition into a 3-D system."""
    if project.system_entry_mode == "import" and not rebuild_imported:
        return import_existing_system(project, progress=progress)
    if project.system_entry_mode == "merge" and not rebuild_imported:
        return merge_existing_systems(project, progress=progress)
    if project.system_entry_mode == "build":
        validate_system_definition(project, progress=progress)
        project.structure.source_mode = "generate"
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, Descriptors
    except ImportError as exc:
        raise RuntimeError("RDKit and NumPy are required to build molecular systems.") from exc

    if not project.molecules:
        raise ValueError("Add at least one molecular species.")
    _report(progress, "RDKit is available; preparing output directories.")
    output_dir = (
        project.output_root / "structure" / "rebuilt_system"
        if rebuild_imported
        else project.output_root / "system"
    )
    molecule_dir = output_dir / "molecule_pdbs"
    output_dir.mkdir(parents=True, exist_ok=True)
    if molecule_dir.exists():
        shutil.rmtree(molecule_dir)
    molecule_dir.mkdir(parents=True)

    total = sum(int(molecule.count) for molecule in project.molecules)
    if total < 1:
        raise ValueError("The system must contain at least one molecule.")
    instances = []
    instance_index = 0
    for molecule in project.molecules:
        if molecule.count < 1:
            raise ValueError(f"{molecule.name} must have a count of at least one.")
        _report(
            progress,
            f"Building and optimizing a 3-D conformer for {molecule.name} "
            f"({molecule.count} molecule(s)).",
        )
        parent = _build_conformer(
            Chem, AllChem, molecule.name, molecule.smiles, project.random_seed + instance_index
        )
        for copy_index in range(1, molecule.count + 1):
            instance_index += 1
            instances.append((molecule, copy_index, Chem.Mol(parent)))

    _report(progress, f"Packing {total} molecule(s) with Sobol placement and clash rejection.")
    packed, packing = _pack_molecules(
        instances,
        Chem,
        Descriptors,
        target_density_kg_m3=project.system_target_density_kg_m3,
        initial_density_fraction=project.system_initial_density_fraction,
        rotate=project.system_rotate_molecules,
        random_seed=project.random_seed,
        progress=progress,
    )
    combined = None
    manifest = {
        "entry_mode": "import-rebuild" if rebuild_imported else "build",
        "topology_source": (
            "Detected composition rebuilt with SMILES conformers and Sobol packing"
            if rebuild_imported
            else "SMILES-generated geometry with Sobol packing"
        ),
        "imported_structure_usable": False,
        "random_seed": project.random_seed,
        "definition_signature": system_definition_signature(project),
        "packing": packing,
        "box": packing["box"],
        "molecules": [],
        "files": {},
    }
    _report(progress, "Writing molecule and combined-system PDB files.")
    for instance_index, ((molecule, copy_index, _), mol) in enumerate(
        zip(instances, packed), start=1
    ):
        instance_name = f"{instance_index:04d}_{_safe_name(molecule.name)}_{copy_index}"
        pdb_path = molecule_dir / f"{instance_name}.pdb"
        Chem.MolToPDBFile(mol, str(pdb_path))
        combined = mol if combined is None else Chem.CombineMols(combined, mol)
        manifest["molecules"].append(
            {
                "instance": instance_name,
                "species_id": molecule.id,
                "name": molecule.name,
                "smiles": molecule.smiles,
                "pdb": str(pdb_path.resolve()),
            }
        )
    system_pdb = output_dir / "system.pdb"
    manifest_path = output_dir / "system_manifest.json"
    Chem.MolToPDBFile(combined, str(system_pdb))
    manifest["files"] = {
        "system_pdb": str(system_pdb.resolve()),
        "manifest": str(manifest_path.resolve()),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _report(progress, f"System artifacts written to {output_dir}.")
    return {
        "molecule_count": total,
        "system_pdb": str(system_pdb),
        "manifest": str(manifest_path),
        "packing": packing,
    }


def _build_conformer(Chem, AllChem, name: str, smiles: str, random_seed: int):
    from rdkit.Geometry import Point3D

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"RDKit could not parse SMILES for {name!r}: {smiles}")
    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=random_seed, useRandomCoords=True) != 0:
        raise RuntimeError(f"RDKit could not embed a 3-D conformer for {name!r}.")
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
    except Exception:
        AllChem.UFFOptimizeMolecule(mol, maxIters=500)
    conf = mol.GetConformer()
    positions = [conf.GetAtomPosition(i) for i in range(conf.GetNumAtoms())]
    center = (
        sum(pos.x for pos in positions) / len(positions),
        sum(pos.y for pos in positions) / len(positions),
        sum(pos.z for pos in positions) / len(positions),
    )
    for index, pos in enumerate(positions):
        conf.SetAtomPosition(index, Point3D(pos.x - center[0], pos.y - center[1], pos.z - center[2]))
    return mol


def _translate(mol, Point3D, offset):
    conf = mol.GetConformer()
    for index in range(conf.GetNumAtoms()):
        pos = conf.GetAtomPosition(index)
        conf.SetAtomPosition(index, Point3D(pos.x + offset[0], pos.y + offset[1], pos.z + offset[2]))


def _pack_molecules(
    instances,
    Chem,
    Descriptors,
    *,
    target_density_kg_m3: float,
    initial_density_fraction: float,
    rotate: bool,
    random_seed: int,
    progress: ProgressCallback | None = None,
):
    """Pack molecule centres on Sobol points with rotations and clash rejection."""
    if target_density_kg_m3 <= 0:
        raise ValueError("Target density must be positive.")
    if not 0 < initial_density_fraction <= 1:
        raise ValueError("Initial density must be greater than 0% and at most 100%.")

    avogadro = 6.02214076e23
    target_density_g_cm3 = target_density_kg_m3 / 1000.0
    total_molar_mass = sum(Descriptors.MolWt(mol) for _, _, mol in instances)
    target_volume_angstrom3 = total_molar_mass / avogadro / target_density_g_cm3 * 1.0e24
    final_length = target_volume_angstrom3 ** (1.0 / 3.0)

    periodic_table = Chem.GetPeriodicTable()
    templates = []
    for original_index, (_, _, mol) in enumerate(instances):
        conformer = mol.GetConformer()
        coordinates = np.asarray(conformer.GetPositions(), dtype=np.float64)
        coordinates -= coordinates.mean(axis=0)
        radii = np.asarray(
            [periodic_table.GetRvdw(atom.GetAtomicNum()) for atom in mol.GetAtoms()],
            dtype=np.float64,
        )
        extent = float(np.max(np.linalg.norm(coordinates, axis=1) + radii))
        templates.append((original_index, mol, coordinates, radii, extent))

    # Largest-first insertion avoids small molecules blocking the few positions
    # suitable for an elongated species. Results are restored to manifest order.
    insertion_order = sorted(templates, key=lambda item: item[4], reverse=True)
    largest_extent = max(item[4] for item in templates)
    minimum_length = 2.0 * largest_extent + 2.0
    box_lengths = np.maximum(
        np.asarray(
            (final_length, final_length, final_length / initial_density_fraction),
            dtype=np.float64,
        ),
        minimum_length,
    )
    rng = np.random.default_rng(int(random_seed))
    clash_scale = 0.72
    rejection_count = 0
    packed_by_index = {}
    expansion_round = 0

    for expansion_round in range(6):
        _report(
            progress,
            f"Packing attempt {expansion_round + 1}: box "
            f"{box_lengths[0]:.2f} × {box_lengths[1]:.2f} × {box_lengths[2]:.2f} Å.",
        )
        candidate_count = max(512, len(instances) * 32)
        skip = int(random_seed % 100_000) + expansion_round * candidate_count
        candidates = _sobol_points_3d(candidate_count, skip)
        candidate_index = 0
        packed_by_index = {}
        stored_positions = []
        stored_radii = []
        cell_size = max(2.5, 2.0 * float(max(np.max(item[3]) for item in templates)) * clash_scale)
        cell_counts = np.maximum(1, np.floor(box_lengths / cell_size).astype(int))
        cell_widths = box_lengths / cell_counts
        bins: dict[tuple[int, int, int], list[int]] = {}

        milestone = max(1, len(instances) // 10)
        for placed_index, (original_index, mol, base_coordinates, radii, extent) in enumerate(
            insertion_order, start=1
        ):
            placed = False
            usable = box_lengths - 2.0 * extent
            if np.any(usable <= 0):
                break
            while candidate_index < candidate_count:
                centre = -0.5 * usable + candidates[candidate_index] * usable
                candidate_index += 1
                rotation = _random_rotation_matrix(rng) if rotate else np.eye(3)
                coordinates = base_coordinates @ rotation.T + centre
                if _coordinates_clash(
                    coordinates,
                    radii,
                    stored_positions,
                    stored_radii,
                    bins,
                    box_lengths,
                    cell_counts,
                    cell_widths,
                    clash_scale,
                ):
                    rejection_count += 1
                    continue
                packed_by_index[original_index] = (mol, coordinates)
                _register_coordinates(
                    coordinates,
                    radii,
                    stored_positions,
                    stored_radii,
                    bins,
                    box_lengths,
                    cell_counts,
                    cell_widths,
                )
                placed = True
                if placed_index % milestone == 0 or placed_index == len(instances):
                    _report(
                        progress,
                        f"Placed {placed_index}/{len(instances)} molecule(s); "
                        f"{rejection_count} clash candidate(s) rejected.",
                    )
                break
            if not placed:
                break

        if len(packed_by_index) == len(instances):
            break
        _report(progress, "Packing did not fit; expanding the box by 20% and retrying.")
        box_lengths *= 1.20
    else:
        raise RuntimeError(
            "Could not create a clash-free Sobol packing after expanding the initial box. "
            "Lower the initial density or inspect unusually large molecular structures."
        )

    from rdkit.Geometry import Point3D

    packed = []
    for index in range(len(instances)):
        mol, coordinates = packed_by_index[index]
        conformer = mol.GetConformer()
        for atom_index, (x, y, z) in enumerate(coordinates):
            conformer.SetAtomPosition(atom_index, Point3D(float(x), float(y), float(z)))
        packed.append(mol)

    half = 0.5 * box_lengths
    actual_fraction = target_volume_angstrom3 / float(np.prod(box_lengths))
    info = {
        "method": "sobol-vdw-rejection",
        "target_density_kg_m3": target_density_kg_m3,
        "requested_initial_density_fraction": initial_density_fraction,
        "actual_initial_density_fraction": actual_fraction,
        "actual_initial_density_kg_m3": target_density_kg_m3 * actual_fraction,
        "target_density_box_length_angstrom": final_length,
        "rotate_molecules": bool(rotate),
        "clash_scale": clash_scale,
        "rejected_candidates": rejection_count,
        "box_expansions": expansion_round,
        "box": {
            "xlo": -float(half[0]),
            "xhi": float(half[0]),
            "ylo": -float(half[1]),
            "yhi": float(half[1]),
            "zlo": -float(half[2]),
            "zhi": float(half[2]),
        },
    }
    return packed, info


def _sobol_points_3d(count: int, skip: int = 0) -> np.ndarray:
    """Return deterministic 3-D Sobol points without an external dependency."""
    if count < 0 or skip < 0:
        raise ValueError("Sobol count and skip must be non-negative.")
    bits = 32
    directions = np.zeros((3, bits), dtype=np.uint32)
    directions[0] = [np.uint32(1 << (31 - index)) for index in range(bits)]

    # Primitive-polynomial parameters for Sobol dimensions 2 and 3.
    for dimension, (degree, coefficient, initial) in enumerate(
        ((1, 0, (1,)), (2, 1, (1, 3))), start=1
    ):
        for index, value in enumerate(initial):
            directions[dimension, index] = np.uint32(value << (31 - index))
        for index in range(degree, bits):
            value = directions[dimension, index - degree]
            value ^= value >> np.uint32(degree)
            for offset in range(1, degree):
                if (coefficient >> (degree - 1 - offset)) & 1:
                    value ^= directions[dimension, index - offset]
            directions[dimension, index] = value

    points = np.empty((count, 3), dtype=np.float64)
    scale = 1.0 / float(1 << bits)
    for output_index, sequence_index in enumerate(range(skip, skip + count)):
        gray = sequence_index ^ (sequence_index >> 1)
        value = np.zeros(3, dtype=np.uint32)
        bit = 0
        while gray:
            if gray & 1:
                value ^= directions[:, bit]
            gray >>= 1
            bit += 1
        points[output_index] = value.astype(np.float64) * scale
    return points


def _random_rotation_matrix(rng):
    """Uniform random rotation using a normalized quaternion."""
    u1, u2, u3 = rng.random(3)
    qx = math.sqrt(1.0 - u1) * math.sin(2.0 * math.pi * u2)
    qy = math.sqrt(1.0 - u1) * math.cos(2.0 * math.pi * u2)
    qz = math.sqrt(u1) * math.sin(2.0 * math.pi * u3)
    qw = math.sqrt(u1) * math.cos(2.0 * math.pi * u3)
    return np.asarray(
        [
            [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
            [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
            [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
        ],
        dtype=np.float64,
    )


def _cell_key(position, box_lengths, cell_counts, cell_widths):
    indices = np.floor((position + 0.5 * box_lengths) / cell_widths).astype(int)
    return tuple(int(value % count) for value, count in zip(indices, cell_counts))


def _coordinates_clash(
    coordinates,
    radii,
    stored_positions,
    stored_radii,
    bins,
    box_lengths,
    cell_counts,
    cell_widths,
    clash_scale,
):
    for position, radius in zip(coordinates, radii):
        cell = _cell_key(position, box_lengths, cell_counts, cell_widths)
        neighbour_indices = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    neighbour = (
                        (cell[0] + dx) % int(cell_counts[0]),
                        (cell[1] + dy) % int(cell_counts[1]),
                        (cell[2] + dz) % int(cell_counts[2]),
                    )
                    neighbour_indices.update(bins.get(neighbour, ()))
        for index in neighbour_indices:
            delta = position - stored_positions[index]
            delta -= box_lengths * np.round(delta / box_lengths)
            limit = clash_scale * (radius + stored_radii[index])
            if float(np.dot(delta, delta)) < limit * limit:
                return True
    return False


def _register_coordinates(
    coordinates,
    radii,
    stored_positions,
    stored_radii,
    bins,
    box_lengths,
    cell_counts,
    cell_widths,
):
    for position, radius in zip(coordinates, radii):
        index = len(stored_positions)
        stored_positions.append(position)
        stored_radii.append(float(radius))
        key = _cell_key(position, box_lengths, cell_counts, cell_widths)
        bins.setdefault(key, []).append(index)


def build_structure(
    project: ScymolProject,
    progress: ProgressCallback | None = None,
    *,
    geometry_manifest: str | Path | None = None,
) -> dict:
    """Assign a PySIMM force field and write a LAMMPS structure.data file."""
    _report(progress, "Reading the prepared geometry manifest.")
    manifest_path = (
        Path(geometry_manifest)
        if geometry_manifest is not None
        else project.output_root / "system" / "system_manifest.json"
    )
    if not manifest_path.exists():
        raise FileNotFoundError("Build or import the molecular system before preparing the LAMMPS structure.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    placement_box = manifest.get("box")
    if not placement_box and project.system_entry_mode in {"import", "merge"}:
        imported_path = Path(manifest.get("imported_structure", ""))
        if imported_path.is_file():
            placement_box = lammps_box_payload(read_lammps_structure(imported_path).box)
            _report(progress, "Recovered the original simulation box from the imported structure.")
    output_dir = project.output_root / "structure"
    output_dir.mkdir(parents=True, exist_ok=True)
    if project.structure.source_mode == "imported":
        _report(progress, "Validating the imported force field for direct reuse.")
        imported = Path(manifest.get("imported_structure", ""))
        if not manifest.get("imported_forcefield_complete") or not imported.is_file():
            raise ValueError(
                "The imported files do not contain a complete reusable force field. "
                "Choose reparameterization while preserving geometry instead."
            )
        destination = output_dir / "structure.data"
        mol_dir = output_dir / "mol_files"
        if mol_dir.exists():
            shutil.rmtree(mol_dir)
        for stale_path in (output_dir / "pysimm.sim.in", output_dir / "temp.lmps"):
            if stale_path.exists():
                stale_path.unlink()
        shutil.copy2(imported, destination)
        _report(progress, f"Copied the imported structure to {destination}.")
        metadata = {
            "mode": "imported",
            "definition_signature": system_definition_signature(project),
            "build_signature": structure_build_signature(project),
            "source": str(imported.resolve()),
            "structure_data": str(destination.resolve()),
            "note": (
                "The last trajectory frame, approved inferred topology, atom types, charges, "
                "and box were preserved. Force-field coefficients must be supplied separately."
                if manifest.get("imported_structure_origin") == "trajectory_snapshot"
                else "The last trajectory frame coordinates and box were combined with the imported LAMMPS structure's topology, types, charges, and coefficients."
                if manifest.get("imported_structure_origin")
                == "structure_with_trajectory_snapshot"
                else "Coordinates, topology, types, charges, box, and any coefficients present were preserved from the imported file."
            ),
            "viewer_bond_orders": [
                record
                for molecule in manifest.get("molecules", [])
                for record in molecule.get("viewer_bond_orders", [])
            ],
        }
        metadata_path = output_dir / "structure_manifest.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        _report(progress, "Imported structure is ready for protocol generation.")
        return {"structure_data": str(destination), "metadata": str(metadata_path), "mode": "imported"}

    _report(progress, "Loading PySIMM and RDKit.")
    try:
        import pysimm.system
        from pysimm import forcefield, lmps
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError as exc:
        raise RuntimeError("PySIMM and RDKit are required to build a LAMMPS structure.") from exc

    mol_dir = output_dir / "mol_files"
    for stale_path in [
        output_dir / "structure.data",
        output_dir / "structure_manifest.json",
        output_dir / "pysimm.sim.in",
        output_dir / "temp.lmps",
    ]:
        if stale_path.exists():
            stale_path.unlink()
    if mol_dir.exists():
        shutil.rmtree(mol_dir)
    mol_dir.mkdir(parents=True)
    try:
        ff = getattr(forcefield, project.structure.forcefield)()
    except AttributeError as exc:
        raise ValueError(f"Unknown PySIMM force field: {project.structure.forcefield}") from exc

    _report(
        progress,
        f"Using {project.structure.forcefield} with {project.structure.charges} charges.",
    )
    combined = None
    positions = []
    converted = []
    viewer_bond_orders = []
    viewer_atom_offset = 0
    typed_species = {}
    reused_instances = 0
    species_by_id = {item.id: item for item in project.molecules}
    for index, molecule in enumerate(manifest.get("molecules", []), start=1):
        species = species_by_id.get(molecule.get("species_id", ""))
        if species is not None:
            molecule = {**molecule, "name": species.name, "smiles": species.smiles}
        if not str(molecule.get("smiles", "")).strip():
            raise ValueError(
                f"Cannot regenerate {molecule.get('name', 'an imported molecule')!r}: "
                "no usable SMILES was detected. Correct its SMILES in Stage 1 or use the imported structure."
            )
        source = Path(molecule["pdb"])
        species_key = (
            molecule.get("species_id") or str(molecule.get("smiles", "")).strip(),
            str(molecule.get("smiles", "")).strip(),
        )
        cached = species_key in typed_species
        action = "Reusing typed species for" if cached else "Typing species for"
        _report(
            progress,
            f"{action} molecule {index}/{len(manifest.get('molecules', []))}: "
            f"{molecule.get('name', molecule.get('instance', 'molecule'))}.",
        )
        mol = _pdb_with_bonds(Chem, AllChem, source, molecule["smiles"], molecule["name"])
        for bond in mol.GetBonds():
            viewer_bond_orders.append(
                {
                    "atoms": [
                        viewer_atom_offset + bond.GetBeginAtomIdx() + 1,
                        viewer_atom_offset + bond.GetEndAtomIdx() + 1,
                    ],
                    "order": (
                        "aromatic"
                        if bond.GetIsAromatic()
                        else float(bond.GetBondTypeAsDouble())
                    ),
                }
            )
        viewer_atom_offset += mol.GetNumAtoms()
        mol_path = mol_dir / f"{index:04d}_{_safe_name(molecule['instance'])}.mol"
        Chem.MolToMolFile(mol, str(mol_path))
        _fix_mol_file(mol_path)
        coordinates = _positions(mol)
        if cached:
            system = _copy_typed_system_with_positions(
                typed_species[species_key],
                coordinates,
                molecule.get("name", molecule.get("instance", "molecule")),
            )
            reused_instances += 1
        else:
            system = pysimm.system.read_mol(str(mol_path))
            system.apply_forcefield(f=ff, charges=project.structure.charges)
            # Keep a pristine typed parent. PySIMM's ``System.add`` mutates IDs
            # while combining systems, so duplicates must be copied from a
            # template that never enters the combined system itself.
            typed_species[species_key] = system.copy()
        combined = system if combined is None else _combine_systems(combined, system)
        positions.extend(coordinates)
        converted.append(
            {
                "source_pdb": str(source),
                "mol": str(mol_path),
                "typing": "reused" if cached else "typed",
                "source_atom_ids": molecule.get("source_atom_ids", []),
            }
        )
    if combined is None:
        raise ValueError("The system manifest does not contain molecules.")
    preserve_imported_geometry = bool(
        project.system_entry_mode in {"import", "merge"}
        and project.structure.source_mode in {"parameterize", "generate"}
        and manifest.get("entry_mode") in {"import", "merge"}
    )
    if preserve_imported_geometry and placement_box:
        _wrap_system_in_box(combined, placement_box)
        _report(progress, "Wrapped typed coordinates into the imported primary simulation box.")
        _assert_positions_preserved(combined, positions, placement_box)
        _report(progress, "Verified that parameterization did not move imported atoms.")
    _set_box(
        combined,
        positions,
        project.structure.box_padding_angstrom,
        placement_box=placement_box,
    )
    _report(progress, "Molecules combined and simulation box assigned.")
    _report(
        progress,
        f"Force-field typing completed for {len(typed_species)} unique species; "
        f"reused typed templates for {reused_instances} molecule(s).",
    )
    _report(progress, "Running PySIMM to write the LAMMPS structure.")
    with _pushd(output_dir):
        simulation = lmps.Simulation(combined, name="scymol_structure")
        pysimm_warning = _run_pysimm_and_promote_input(simulation, progress=progress)
    metadata = {
        "mode": (
            "parameterized-import"
            if preserve_imported_geometry
            else "rebuilt-import"
            if project.structure.source_mode == "rebuild"
            else "generated"
        ),
        "definition_signature": system_definition_signature(project),
        "build_signature": structure_build_signature(project),
        "input_manifest": str(manifest_path),
        "forcefield": project.structure.forcefield,
        "charges": project.structure.charges,
        "box_padding_angstrom": project.structure.box_padding_angstrom,
        "packing": manifest.get("packing", {}),
        "placement_box_preserved": bool(placement_box),
        "imported_positions_preserved": preserve_imported_geometry,
        "position_check_tolerance_angstrom": 1.0e-5 if preserve_imported_geometry else None,
        "converted_molecules": converted,
        "typing_cache": {
            "unique_species_typed": len(typed_species),
            "instances_reused": reused_instances,
        },
        "pysimm_warning": pysimm_warning,
        "viewer_bond_orders": viewer_bond_orders,
    }
    metadata_path = output_dir / "structure_manifest.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _report(progress, f"LAMMPS structure written to {output_dir / 'structure.data'}.")
    return {"structure_data": str(output_dir / "structure.data"), "metadata": str(metadata_path)}


def _run_pysimm_and_promote_input(
    simulation, progress: ProgressCallback | None = None
) -> str | None:
    """Run PySIMM's input writer and preserve its known post-write TypeError behavior.

    Some PySIMM versions successfully create ``temp.lmps`` and subsequently
    raise ``TypeError`` while handling an optional path. That exception is a
    warning only when the expected temporary input actually exists.
    """
    warning = None
    try:
        simulation.run(save_input=True)
    except TypeError as exc:
        warning = f"PySIMM raised TypeError after writing its input: {exc}"
        _report(progress, f"Warning: {warning}")

    temp_input = Path("temp.lmps")
    if not temp_input.exists():
        detail = f" The preceding PySIMM warning was: {warning}" if warning else ""
        raise RuntimeError(f"PySIMM did not write temp.lmps.{detail}")
    temp_input.replace("structure.data")
    _report(progress, "PySIMM completed and its generated input was promoted to structure.data.")
    return warning


def _combine_systems(combined, system):
    combined.add(system, change_dim=True)
    return combined


def _copy_typed_system_with_positions(template, coordinates, name: str):
    """Clone a typed PySIMM species and apply one packed instance's positions."""
    copied = template.copy()
    particles = list(copied.particles)
    if len(particles) != len(coordinates):
        raise ValueError(
            f"Cannot reuse force-field typing for {name!r}: the typed template has "
            f"{len(particles)} atoms but this instance has {len(coordinates)} coordinates."
        )
    for particle, (x, y, z) in zip(particles, coordinates):
        particle.x = float(x)
        particle.y = float(y)
        particle.z = float(z)
    return copied


def _pdb_with_bonds(Chem, AllChem, path: Path, smiles: str, name: str):
    pdb_mol = Chem.MolFromPDBFile(str(path), removeHs=False, sanitize=False)
    if pdb_mol is None:
        raise ValueError(f"RDKit could not read PDB for {name!r}: {path}")
    template = Chem.MolFromSmiles(smiles)
    if template is None:
        raise ValueError(f"RDKit could not parse SMILES for {name!r}: {smiles}")
    try:
        mol = AllChem.AssignBondOrdersFromTemplate(Chem.AddHs(template), pdb_mol)
    except Exception:
        mol = pdb_mol
    Chem.SanitizeMol(mol)
    return mol


def _positions(mol):
    conf = mol.GetConformer()
    result = []
    for index in range(conf.GetNumAtoms()):
        point = conf.GetAtomPosition(index)
        result.append((point.x, point.y, point.z))
    return result


def _set_box(system, positions, padding: float, placement_box=None):
    if placement_box:
        required = ("xlo", "xhi", "ylo", "yhi", "zlo", "zhi")
        try:
            values = {key: float(placement_box[key]) for key in required}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("The 3-D placement box is malformed.") from exc
        system.dim.xlo, system.dim.xhi = values["xlo"], values["xhi"]
        system.dim.ylo, system.dim.yhi = values["ylo"], values["yhi"]
        system.dim.zlo, system.dim.zhi = values["zlo"], values["zhi"]
        return
    xs, ys, zs = zip(*positions)
    system.dim.xlo, system.dim.xhi = min(xs) - padding, max(xs) + padding
    system.dim.ylo, system.dim.yhi = min(ys) - padding, max(ys) + padding
    system.dim.zlo, system.dim.zhi = min(zs) - padding, max(zs) + padding


def _wrap_system_in_box(system, placement_box):
    required = ("xlo", "xhi", "ylo", "yhi", "zlo", "zhi")
    try:
        values = {key: float(placement_box[key]) for key in required}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("The imported simulation box is malformed.") from exc
    bounds = (
        (values["xlo"], values["xhi"]),
        (values["ylo"], values["yhi"]),
        (values["zlo"], values["zhi"]),
    )
    for particle in system.particles:
        for axis, (low, high) in zip("xyz", bounds):
            length = high - low
            if length <= 0.0:
                raise ValueError("The imported simulation box has invalid bounds.")
            coordinate = float(getattr(particle, axis))
            setattr(particle, axis, low + ((coordinate - low) % length))


def _assert_positions_preserved(system, expected_positions, placement_box, tolerance=1.0e-5):
    particles = list(system.particles)
    if len(particles) != len(expected_positions):
        raise RuntimeError(
            "Parameterization changed the imported atom count; refusing to write the structure."
        )
    bounds = tuple(
        (float(placement_box[f"{axis}lo"]), float(placement_box[f"{axis}hi"]))
        for axis in "xyz"
    )
    for atom_index, (particle, expected) in enumerate(
        zip(particles, expected_positions), start=1
    ):
        actual = (float(particle.x), float(particle.y), float(particle.z))
        for axis, (observed, requested, (low, high)) in enumerate(
            zip(actual, expected, bounds)
        ):
            length = high - low
            requested_wrapped = low + ((float(requested) - low) % length)
            delta = observed - requested_wrapped
            delta -= length * round(delta / length)
            if abs(delta) > tolerance:
                axis_name = "xyz"[axis]
                raise RuntimeError(
                    f"Parameterization moved atom {atom_index} along {axis_name}; "
                    "the imported geometry was not written."
                )


def _fix_mol_file(path: Path):
    fixed = path.with_name(path.stem + "_fixed.mol")
    with path.open("r") as source, fixed.open("w") as destination:
        for line in source:
            parts = line.split()
            if len(parts) in {10, 3} and len(parts[0]) > 3:
                parts[0] = parts[0][:-3] + " " + parts[0][-3:]
                destination.write((" " if len(parts) == 3 else "") + " ".join(parts) + "\n")
            else:
                destination.write(line)
    fixed.replace(path)


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in name)


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)
