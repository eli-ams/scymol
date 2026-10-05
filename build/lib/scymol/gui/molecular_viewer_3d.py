"""Self-contained high-throughput 3D viewer used by Scymol Stage 2.

Atoms are rendered as one GL point each. Bonds are rendered as one instanced
camera-facing capsule each. Camera interaction only updates two matrices; no
geometry is rebuilt while orbiting, panning, or zooming.
"""

from __future__ import annotations

import math
import re
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import moderngl
import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import (
    QCloseEvent,
    QKeyEvent,
    QMouseEvent,
    QOpenGLContext,
    QSurfaceFormat,
    QWheelEvent,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


BACKGROUND = (1.0, 1.0, 1.0, 1.0)

# ---------------------------------------------------------------------------
# Configuration: edit these Python variables, then run molecule_viewer.py.
# Set BENCHMARK_ATOMS to 1_000_000 to test particle throughput; keep it at 0
# to generate the molecule defined by SMILES.
# ---------------------------------------------------------------------------
SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"  # Aspirin
EMBEDDING_SEED = 61_453
ATOM_SCALE = 0.34
BOND_RADIUS = 0.13
BOND_SEPARATION = 0.32
AROMATIC_DASH_COUNT = 5.0
FAST_DEPTH = False
BENCHMARK_ATOMS = 0
BENCHMARK_EXTENT = 400.0

# Optional LAMMPS overrides. Values in LAMMPS_TYPE_ELEMENTS may be atomic
# numbers (6) or symbols ("C"). Bond values may be 1, 2, 3, or "aromatic".
LAMMPS_TYPE_ELEMENTS: dict[int, int | str] = {}
LAMMPS_BOND_ORDERS: dict[int, float | str] = {}
TRAJECTORY_CACHE_FRAMES = 3
IDLE_ANTIALIAS_SAMPLES = 4
IDLE_ANTIALIAS_DELAY_MS = 140
GL_SAMPLE_ALPHA_TO_COVERAGE = 0x809E

# CPK/Jmol-like colours. Unknown elements use the fallback colour.
ELEMENT_COLOURS = {
    1: (1.00, 1.00, 1.00),
    6: (0.24, 0.26, 0.31),
    7: (0.19, 0.31, 0.97),
    8: (0.95, 0.16, 0.14),
    9: (0.36, 0.90, 0.38),
    15: (1.00, 0.50, 0.00),
    16: (1.00, 0.82, 0.12),
    17: (0.12, 0.82, 0.22),
    35: (0.65, 0.16, 0.16),
    53: (0.45, 0.12, 0.60),
}
FALLBACK_COLOUR = (0.62, 0.66, 0.72)


@dataclass(slots=True)
class SceneData:
    atom_data: np.ndarray
    bond_data: np.ndarray
    chemical_bond_count: int
    centre: np.ndarray
    radius: float
    label: str
    atom_ids: np.ndarray | None = None
    bond_indices: np.ndarray | None = None
    bond_offsets: np.ndarray | None = None
    topology_bond_indices: np.ndarray | None = None
    cell_matrix: np.ndarray | None = None
    periodic: np.ndarray | None = None
    positions_wrapped: bool = False


@dataclass(slots=True, frozen=True)
class DumpFrameInfo:
    atom_offset: int
    timestep: int
    atom_count: int
    columns: tuple[str, ...]
    bounds: np.ndarray
    tilt: np.ndarray
    periodic: np.ndarray


@dataclass(slots=True)
class DumpFrameData:
    index: int
    timestep: int
    atom_ids: np.ndarray
    positions: np.ndarray
    cell_matrix: np.ndarray
    periodic: np.ndarray
    positions_wrapped: bool


def _interleaved_atoms(
    positions: np.ndarray, radii: np.ndarray, colours: np.ndarray
) -> np.ndarray:
    data = np.empty((len(positions), 7), dtype="f4")
    data[:, :3] = positions
    data[:, 3] = radii
    data[:, 4:] = colours
    return np.ascontiguousarray(data)


def _interleaved_bonds(
    starts: np.ndarray,
    ends: np.ndarray,
    radii: np.ndarray,
    start_colours: np.ndarray,
    end_colours: np.ndarray,
    dash_counts: np.ndarray,
) -> np.ndarray:
    data = np.empty((len(starts), 14), dtype="f4")
    data[:, 0:3] = starts
    data[:, 3:6] = ends
    data[:, 6] = radii
    data[:, 7:10] = start_colours
    data[:, 10:13] = end_colours
    data[:, 13] = dash_counts
    return np.ascontiguousarray(data)


def _bond_render_specs(order: float, aromatic: bool) -> tuple[tuple[float, float, float], ...]:
    """Return (offset multiplier, radius multiplier, dash count) per impostor."""
    if aromatic:
        # The positive offset points towards the aromatic ring centre.
        return ((-0.5, 1.0, 0.0), (0.5, 0.78, AROMATIC_DASH_COUNT))
    if order >= 2.75:
        return ((-1.0, 0.82, 0.0), (0.0, 0.82, 0.0), (1.0, 0.82, 0.0))
    if order >= 1.75:
        return ((-0.5, 0.90, 0.0), (0.5, 0.90, 0.0))
    return ((0.0, 1.0, 0.0),)


def _bond_offset_direction(molecule, positions: np.ndarray, bond) -> np.ndarray:
    """Find a stable local-plane direction perpendicular to a bond."""
    a = bond.GetBeginAtomIdx()
    b = bond.GetEndAtomIdx()
    axis = positions[b] - positions[a]
    axis_length = float(np.linalg.norm(axis))
    if axis_length < 1e-7:
        return np.array((1.0, 0.0, 0.0), dtype="f4")
    axis /= axis_length

    references: list[np.ndarray] = []
    if bond.GetIsAromatic() and bond.IsInRing():
        rings = [
            ring
            for ring in molecule.GetRingInfo().AtomRings()
            if a in ring and b in ring
        ]
        if rings:
            ring = min(rings, key=len)
            ring_centre = positions[np.asarray(ring, dtype=np.int32)].mean(axis=0)
            references.append(ring_centre - 0.5 * (positions[a] + positions[b]))

    # A neighbouring atom defines the local molecular plane.
    for atom_index, excluded_index in ((a, b), (b, a)):
        atom = molecule.GetAtomWithIdx(atom_index)
        for neighbour in atom.GetNeighbors():
            neighbour_index = neighbour.GetIdx()
            if neighbour_index != excluded_index:
                references.append(positions[neighbour_index] - positions[atom_index])

    # A global-axis fallback handles isolated multiple bonds such as O=O.
    fallback_axis = np.zeros(3, dtype="f4")
    fallback_axis[int(np.argmin(np.abs(axis)))] = 1.0
    references.append(fallback_axis)
    for reference in references:
        perpendicular = reference - axis * float(np.dot(reference, axis))
        length = float(np.linalg.norm(perpendicular))
        if length > 1e-6:
            return np.asarray(perpendicular / length, dtype="f4")
    return np.array((1.0, 0.0, 0.0), dtype="f4")


def scene_from_smiles(
    smiles: str,
    atom_scale: float,
    bond_radius: float,
    bond_separation: float,
    seed: int,
) -> SceneData:
    """Build and optimise one hydrogen-complete RDKit conformer."""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError as exc:
        raise SystemExit(
            "SMILES conversion requires RDKit. Install requirements with:\n"
            "  python -m pip install -r requirements.txt"
        ) from exc

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise SystemExit(f"RDKit could not parse SMILES: {smiles!r}")
    molecule = Chem.AddHs(molecule)

    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    params.useRandomCoords = False
    status = AllChem.EmbedMolecule(molecule, params)
    if status != 0:
        params.useRandomCoords = True
        status = AllChem.EmbedMolecule(molecule, params)
    if status != 0:
        raise SystemExit("RDKit failed to generate a 3D conformer for this SMILES.")

    if AllChem.MMFFHasAllMoleculeParams(molecule):
        AllChem.MMFFOptimizeMolecule(molecule, maxIters=500)
    else:
        AllChem.UFFOptimizeMolecule(molecule, maxIters=500)

    conformer = molecule.GetConformer()
    positions = np.asarray(conformer.GetPositions(), dtype="f4")
    centre = positions.mean(axis=0, dtype=np.float64).astype("f4")
    positions -= centre
    centre = np.zeros(3, dtype="f4")

    periodic_table = Chem.GetPeriodicTable()
    atomic_numbers = np.fromiter(
        (atom.GetAtomicNum() for atom in molecule.GetAtoms()),
        dtype=np.int32,
        count=molecule.GetNumAtoms(),
    )
    radii = np.fromiter(
        (periodic_table.GetRvdw(int(number)) for number in atomic_numbers),
        dtype=np.float32,
        count=len(atomic_numbers),
    )
    radii *= np.float32(atom_scale)
    colours = np.asarray(
        [ELEMENT_COLOURS.get(int(number), FALLBACK_COLOUR) for number in atomic_numbers],
        dtype="f4",
    )

    starts: list[np.ndarray] = []
    ends: list[np.ndarray] = []
    start_colours: list[np.ndarray] = []
    end_colours: list[np.ndarray] = []
    bond_radii: list[float] = []
    dash_counts: list[float] = []
    for bond in molecule.GetBonds():
        a = bond.GetBeginAtomIdx()
        b = bond.GetEndAtomIdx()
        order = float(bond.GetBondTypeAsDouble())
        aromatic = bool(bond.GetIsAromatic())
        render_specs = _bond_render_specs(order, aromatic)
        offset_direction = (
            _bond_offset_direction(molecule, positions, bond)
            if len(render_specs) > 1
            else np.zeros(3, dtype="f4")
        )
        for offset_scale, radius_scale, dash_count in render_specs:
            offset = offset_direction * np.float32(bond_separation * offset_scale)
            starts.append(positions[a] + offset)
            ends.append(positions[b] + offset)
            start_colours.append(colours[a])
            end_colours.append(colours[b])
            bond_radii.append(bond_radius * radius_scale)
            dash_counts.append(dash_count)

    primitive_count = len(starts)
    starts_array = np.asarray(starts, dtype="f4").reshape(primitive_count, 3)
    ends_array = np.asarray(ends, dtype="f4").reshape(primitive_count, 3)
    start_colours_array = np.asarray(start_colours, dtype="f4").reshape(primitive_count, 3)
    end_colours_array = np.asarray(end_colours, dtype="f4").reshape(primitive_count, 3)

    extent = np.linalg.norm(positions, axis=1) + radii
    scene_radius = max(float(extent.max(initial=1.0)), 1.0)
    return SceneData(
        atom_data=_interleaved_atoms(positions, radii, colours),
        bond_data=_interleaved_bonds(
            starts_array,
            ends_array,
            np.asarray(bond_radii, dtype="f4"),
            start_colours_array,
            end_colours_array,
            np.asarray(dash_counts, dtype="f4"),
        ),
        chemical_bond_count=molecule.GetNumBonds(),
        centre=centre,
        radius=scene_radius,
        label=smiles,
    )


def benchmark_scene(count: int, extent: float, seed: int) -> SceneData:
    """Generate a repeatable, bond-free cloud for throughput measurements."""
    if count < 1:
        raise SystemExit("BENCHMARK_ATOMS must be at least 1")
    rng = np.random.default_rng(seed)
    positions = rng.uniform(-extent, extent, size=(count, 3)).astype("f4")
    radii = np.full(count, max(extent * 0.0018, 0.18), dtype="f4")
    colours = np.empty((count, 3), dtype="f4")
    # Colour without allocating extra random arrays.
    colours[:, 0] = 0.28 + 0.18 * (positions[:, 1] / extent + 1.0)
    colours[:, 1] = 0.58 + 0.17 * (positions[:, 2] / extent + 1.0)
    colours[:, 2] = 0.88
    return SceneData(
        atom_data=_interleaved_atoms(positions, radii, colours),
        bond_data=np.empty((0, 14), dtype="f4"),
        chemical_bond_count=0,
        centre=np.zeros(3, dtype="f4"),
        radius=float(extent * math.sqrt(3.0)),
        label=f"benchmark {count:,} atoms",
    )


_LAMMPS_SECTIONS = {
    "Masses",
    "Atoms",
    "Bonds",
    "Velocities",
    "Angles",
    "Dihedrals",
    "Impropers",
    "Pair Coeffs",
    "PairIJ Coeffs",
    "Bond Coeffs",
    "Angle Coeffs",
    "Dihedral Coeffs",
    "Improper Coeffs",
    "Atom Type Labels",
    "Bond Type Labels",
}

_ATOM_STYLE_LAYOUTS = {
    "atomic": (1, 2),
    "charge": (1, 3),
    "molecular": (2, 3),
    "bond": (2, 3),
    "angle": (2, 3),
    "full": (2, 4),
    "sphere": (1, 4),
    "ellipsoid": (1, 4),
    "line": (2, 5),
    "body": (1, 4),
    "hybrid": (1, 2),
}


def _is_integer_token(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _infer_atom_layout(
    values: list[str], atom_style: str, atom_type_count: int
) -> tuple[int, int]:
    if atom_style in _ATOM_STYLE_LAYOUTS:
        return _ATOM_STYLE_LAYOUTS[atom_style]
    # Practical fallback for data files lacking the recommended "Atoms # style".
    field_count = len(values)
    if field_count in (5, 8):
        return 1, 2  # atomic, optionally followed by image flags
    if field_count in (7, 10):
        return 2, 4  # full, optionally followed by image flags
    if field_count in (6, 9):
        third_is_type = _is_integer_token(values[2]) and (
            atom_type_count <= 0 or 1 <= int(values[2]) <= atom_type_count
        )
        return (2, 3) if third_is_type else (1, 3)  # molecular or charge
    raise ValueError(
        "Cannot infer the LAMMPS atom style. Add a style comment such as "
        "'Atoms # full' to the data file."
    )


def _element_for_lammps_type(
    atom_type: int, mass: float | None, comment: str, periodic_table
) -> int:
    override = LAMMPS_TYPE_ELEMENTS.get(atom_type)
    if override is not None:
        if isinstance(override, str):
            atomic_number = int(periodic_table.GetAtomicNumber(override))
        else:
            atomic_number = int(override)
        if atomic_number < 1:
            raise ValueError(f"Invalid element override for LAMMPS atom type {atom_type}")
        return atomic_number

    comment_symbol = comment.split()[0] if comment else ""
    if re.fullmatch(r"[A-Z][a-z]?", comment_symbol):
        atomic_number = int(periodic_table.GetAtomicNumber(comment_symbol))
        if atomic_number:
            return atomic_number

    if mass is None:
        return 6
    return min(
        range(1, 119),
        key=lambda number: abs(float(periodic_table.GetAtomicWeight(number)) - mass),
    )


def _topology_offset_direction(
    positions: np.ndarray,
    atom_a: int,
    atom_b: int,
    adjacency: list[list[int]],
) -> np.ndarray:
    axis = positions[atom_b] - positions[atom_a]
    axis_length = float(np.linalg.norm(axis))
    if axis_length < 1e-7:
        return np.array((1.0, 0.0, 0.0), dtype="f4")
    axis /= axis_length
    references = [
        positions[neighbour] - positions[owner]
        for owner, excluded in ((atom_a, atom_b), (atom_b, atom_a))
        for neighbour in adjacency[owner]
        if neighbour != excluded
    ]
    fallback = np.zeros(3, dtype="f4")
    fallback[int(np.argmin(np.abs(axis)))] = 1.0
    references.append(fallback)
    for reference in references:
        perpendicular = reference - axis * float(np.dot(reference, axis))
        length = float(np.linalg.norm(perpendicular))
        if length > 1e-6:
            return np.asarray(perpendicular / length, dtype="f4")
    return np.array((1.0, 0.0, 0.0), dtype="f4")


def scene_from_lammps_data(
    path: str | Path,
    bond_type_orders: dict[int, float | str] | None = None,
    bond_pair_orders: dict[tuple[int, int], float | str] | None = None,
) -> SceneData:
    """Read atom types, positions, masses, and bond topology from a data file."""
    try:
        from rdkit import Chem
    except ImportError as exc:
        raise RuntimeError("LAMMPS element inference requires RDKit") from exc

    path = Path(path)
    type_orders = bond_type_orders or LAMMPS_BOND_ORDERS
    pair_orders = bond_pair_orders or {}
    atom_style = ""
    atom_type_count = 0
    section = ""
    masses: dict[int, tuple[float, str]] = {}
    atoms: list[tuple[int, int, float, float, float]] = []
    bonds: list[tuple[int, int, int]] = []
    box: dict[str, tuple[float, float]] = {}
    tilt = np.zeros(3, dtype="f8")

    with path.open("rt", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue
            content, _, comment = stripped.partition("#")
            content = content.strip()
            comment = comment.strip()
            if not content:
                continue

            if content[0].isalpha():
                section = content if content in _LAMMPS_SECTIONS else ""
                if section == "Atoms":
                    atom_style = comment.split()[0].lower() if comment else ""
                continue

            values = content.split()
            if not section:
                if content.endswith(" atom types"):
                    atom_type_count = int(values[0])
                elif content.endswith(" xlo xhi"):
                    box["x"] = (float(values[0]), float(values[1]))
                elif content.endswith(" ylo yhi"):
                    box["y"] = (float(values[0]), float(values[1]))
                elif content.endswith(" zlo zhi"):
                    box["z"] = (float(values[0]), float(values[1]))
                elif content.endswith(" xy xz yz"):
                    tilt[:] = (float(values[0]), float(values[1]), float(values[2]))
                continue

            if section == "Masses":
                masses[int(values[0])] = (float(values[1]), comment)
            elif section == "Atoms":
                type_index, coordinate_index = _infer_atom_layout(
                    values, atom_style, atom_type_count
                )
                atoms.append(
                    (
                        int(values[0]),
                        int(values[type_index]),
                        float(values[coordinate_index]),
                        float(values[coordinate_index + 1]),
                        float(values[coordinate_index + 2]),
                    )
                )
            elif section == "Bonds":
                bonds.append((int(values[1]), int(values[2]), int(values[3])))

    if not atoms:
        raise ValueError(f"No atoms were found in {path.name}")

    atoms.sort(key=lambda atom: atom[0])
    atom_ids = np.fromiter((atom[0] for atom in atoms), dtype=np.int64)
    atom_types = np.fromiter((atom[1] for atom in atoms), dtype=np.int32)
    positions = np.asarray([atom[2:] for atom in atoms], dtype="f4")
    cell_matrix = None
    if all(axis in box for axis in "xyz"):
        xlo, xhi = box["x"]
        ylo, yhi = box["y"]
        zlo, zhi = box["z"]
        xy, xz, yz = tilt
        origin = np.asarray(
            (
                xlo + 0.5 * ((xhi - xlo) + xy + xz),
                ylo + 0.5 * ((yhi - ylo) + yz),
                zlo + 0.5 * (zhi - zlo),
            ),
            dtype="f4",
        )
        cell_matrix = np.asarray(
            (
                (xhi - xlo, xy, xz),
                (0.0, yhi - ylo, yz),
                (0.0, 0.0, zhi - zlo),
            ),
            dtype="f4",
        )
    else:
        origin = positions.mean(axis=0, dtype=np.float64).astype("f4")
    positions -= origin

    periodic_table = Chem.GetPeriodicTable()
    type_elements: dict[int, int] = {}
    for atom_type in np.unique(atom_types):
        mass_entry = masses.get(int(atom_type))
        type_elements[int(atom_type)] = _element_for_lammps_type(
            int(atom_type),
            mass_entry[0] if mass_entry else None,
            mass_entry[1] if mass_entry else "",
            periodic_table,
        )
    atomic_numbers = np.asarray(
        [type_elements[int(atom_type)] for atom_type in atom_types], dtype=np.int32
    )
    radii = np.fromiter(
        (periodic_table.GetRvdw(int(number)) for number in atomic_numbers),
        dtype=np.float32,
        count=len(atomic_numbers),
    )
    radii *= np.float32(ATOM_SCALE)
    colours = np.asarray(
        [ELEMENT_COLOURS.get(int(number), FALLBACK_COLOUR) for number in atomic_numbers],
        dtype="f4",
    )

    id_to_index = {int(atom_id): index for index, atom_id in enumerate(atom_ids)}
    indexed_bonds: list[tuple[int, int, int]] = []
    adjacency: list[list[int]] = [[] for _ in range(len(atom_ids))]
    for bond_type, atom_a_id, atom_b_id in bonds:
        try:
            atom_a = id_to_index[atom_a_id]
            atom_b = id_to_index[atom_b_id]
        except KeyError as exc:
            raise ValueError(f"Bond references missing atom ID {exc.args[0]}") from exc
        indexed_bonds.append((bond_type, atom_a, atom_b))
        adjacency[atom_a].append(atom_b)
        adjacency[atom_b].append(atom_a)

    starts: list[np.ndarray] = []
    ends: list[np.ndarray] = []
    start_colours: list[np.ndarray] = []
    end_colours: list[np.ndarray] = []
    bond_radii: list[float] = []
    dash_counts: list[float] = []
    primitive_indices: list[tuple[int, int]] = []
    primitive_offsets: list[np.ndarray] = []
    for bond_type, atom_a, atom_b in indexed_bonds:
        atom_a_id = int(atom_ids[atom_a])
        atom_b_id = int(atom_ids[atom_b])
        pair = tuple(sorted((atom_a_id, atom_b_id)))
        configured_order = pair_orders.get(pair, type_orders.get(bond_type, 1.0))
        aromatic = str(configured_order).lower() == "aromatic"
        order = 1.5 if aromatic else float(configured_order)
        specs = _bond_render_specs(order, aromatic)
        direction = (
            _topology_offset_direction(positions, atom_a, atom_b, adjacency)
            if len(specs) > 1
            else np.zeros(3, dtype="f4")
        )
        for offset_scale, radius_scale, dash_count in specs:
            offset = direction * np.float32(BOND_SEPARATION * offset_scale)
            starts.append(positions[atom_a] + offset)
            ends.append(positions[atom_b] + offset)
            start_colours.append(colours[atom_a])
            end_colours.append(colours[atom_b])
            bond_radii.append(BOND_RADIUS * radius_scale)
            dash_counts.append(dash_count)
            primitive_indices.append((atom_a, atom_b))
            primitive_offsets.append(offset)

    primitive_count = len(starts)
    vector_array = lambda values: np.asarray(values, dtype="f4").reshape(primitive_count, 3)
    extent = np.linalg.norm(positions, axis=1) + radii
    scene_radius = max(float(extent.max(initial=1.0)), 1.0)
    if cell_matrix is not None:
        fractional_corners = np.asarray(
            [
                (x, y, z)
                for x in (-0.5, 0.5)
                for y in (-0.5, 0.5)
                for z in (-0.5, 0.5)
            ],
            dtype="f4",
        )
        cell_corners = fractional_corners @ cell_matrix.T
        scene_radius = max(
            scene_radius,
            float(np.linalg.norm(cell_corners, axis=1).max(initial=1.0)),
        )
    return SceneData(
        atom_data=_interleaved_atoms(positions, radii, colours),
        bond_data=_interleaved_bonds(
            vector_array(starts),
            vector_array(ends),
            np.asarray(bond_radii, dtype="f4"),
            vector_array(start_colours),
            vector_array(end_colours),
            np.asarray(dash_counts, dtype="f4"),
        ),
        chemical_bond_count=len(indexed_bonds),
        centre=np.zeros(3, dtype="f4"),
        radius=scene_radius,
        label=path.name,
        atom_ids=atom_ids,
        bond_indices=np.asarray(primitive_indices, dtype=np.int32).reshape(
            primitive_count, 2
        ),
        bond_offsets=vector_array(primitive_offsets),
        topology_bond_indices=np.asarray(
            [(atom_a, atom_b) for _, atom_a, atom_b in indexed_bonds],
            dtype=np.int32,
        ).reshape(len(indexed_bonds), 2),
        cell_matrix=cell_matrix,
        periodic=np.ones(3, dtype=bool) if cell_matrix is not None else None,
        positions_wrapped=cell_matrix is not None,
    )


def _restricted_box_geometry(
    raw_bounds: np.ndarray, tilt: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xy, xz, yz = (float(value) for value in tilt)
    xlo = raw_bounds[0, 0] - min(0.0, xy, xz, xy + xz)
    xhi = raw_bounds[0, 1] - max(0.0, xy, xz, xy + xz)
    ylo = raw_bounds[1, 0] - min(0.0, yz)
    yhi = raw_bounds[1, 1] - max(0.0, yz)
    zlo, zhi = raw_bounds[2]
    origin = np.asarray((xlo, ylo, zlo), dtype="f8")
    lengths = np.asarray((xhi - xlo, yhi - ylo, zhi - zlo), dtype="f8")
    centre = origin + np.asarray(
        (0.5 * (lengths[0] + xy + xz), 0.5 * (lengths[1] + yz), 0.5 * lengths[2]),
        dtype="f8",
    )
    cell_matrix = np.asarray(
        (
            (lengths[0], xy, xz),
            (0.0, lengths[1], yz),
            (0.0, 0.0, lengths[2]),
        ),
        dtype="f8",
    )
    return origin, lengths, centre, cell_matrix


class LammpsDumpTrajectory:
    """Byte-indexed LAMMPS text dump with a small on-demand frame cache."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.frames: list[DumpFrameInfo] = []
        self._cache: OrderedDict[int, DumpFrameData] = OrderedDict()

    def build_index(self) -> "LammpsDumpTrajectory":
        with self.path.open("rb") as handle:
            while True:
                line = handle.readline()
                if not line:
                    break
                if not line.startswith(b"ITEM: TIMESTEP"):
                    continue
                timestep = int(handle.readline().strip())
                marker = handle.readline()
                if not marker.startswith(b"ITEM: NUMBER OF ATOMS"):
                    raise ValueError("Expected 'ITEM: NUMBER OF ATOMS' in trajectory")
                atom_count = int(handle.readline().strip())
                box_header = handle.readline().decode("ascii", errors="replace").strip()
                if not box_header.startswith("ITEM: BOX BOUNDS"):
                    raise ValueError("Expected 'ITEM: BOX BOUNDS' in trajectory")
                bound_rows = [
                    [float(value) for value in handle.readline().split()]
                    for _ in range(3)
                ]
                raw_bounds = np.asarray([row[:2] for row in bound_rows], dtype="f8")
                tilt = np.zeros(3, dtype="f8")
                if all(len(row) >= 3 for row in bound_rows):
                    tilt[:] = (bound_rows[0][2], bound_rows[1][2], bound_rows[2][2])
                boundary_tokens = [
                    token.lower()
                    for token in box_header.split()[3:]
                    if len(token) == 2 and all(char in "pfsm" for char in token.lower())
                ]
                periodic = (
                    np.asarray([token == "pp" for token in boundary_tokens[-3:]], dtype=bool)
                    if len(boundary_tokens) >= 3
                    else np.ones(3, dtype=bool)
                )
                atom_header = handle.readline().decode("ascii", errors="replace").strip()
                if not atom_header.startswith("ITEM: ATOMS "):
                    raise ValueError("Expected an 'ITEM: ATOMS ...' column header")
                columns = tuple(atom_header.split()[2:])
                atom_offset = handle.tell()
                self.frames.append(
                    DumpFrameInfo(
                        atom_offset,
                        timestep,
                        atom_count,
                        columns,
                        raw_bounds,
                        tilt,
                        periodic,
                    )
                )
                for _ in range(atom_count):
                    if not handle.readline():
                        raise ValueError("Trajectory ended inside an atom frame")
        if not self.frames:
            raise ValueError(f"No LAMMPS dump frames found in {self.path.name}")
        return self

    def load_frame(self, index: int) -> DumpFrameData:
        cached = self._cache.get(index)
        if cached is not None:
            self._cache.move_to_end(index)
            return cached
        info = self.frames[index]
        column_indices = {name: position for position, name in enumerate(info.columns)}
        if "id" not in column_indices:
            raise ValueError("Trajectory must include an 'id' atom column")

        coordinate_names: tuple[str, str, str] | None = None
        scaled = False
        positions_wrapped = True
        for names, is_scaled, is_wrapped in (
            (("xu", "yu", "zu"), False, False),
            (("x", "y", "z"), False, True),
            (("xsu", "ysu", "zsu"), True, False),
            (("xs", "ys", "zs"), True, True),
        ):
            if all(name in column_indices for name in names):
                coordinate_names = names
                scaled = is_scaled
                positions_wrapped = is_wrapped
                break
        if coordinate_names is None:
            raise ValueError("Trajectory needs x/y/z, xu/yu/zu, xs/ys/zs, or xsu/ysu/zsu")

        use_columns = (column_indices["id"],) + tuple(
            column_indices[name] for name in coordinate_names
        )
        with self.path.open("rb") as handle:
            handle.seek(info.atom_offset)
            values = np.loadtxt(
                handle,
                dtype=np.float64,
                usecols=use_columns,
                max_rows=info.atom_count,
                ndmin=2,
            )
        if len(values) != info.atom_count:
            raise ValueError(f"Frame {index} contains fewer atoms than declared")
        atom_ids = values[:, 0].astype(np.int64)
        positions = values[:, 1:4]
        origin, lengths, centre, cell_matrix = _restricted_box_geometry(
            info.bounds, info.tilt
        )
        if scaled:
            xy, xz, yz = info.tilt
            scaled_positions = positions
            positions = np.empty_like(scaled_positions)
            positions[:, 0] = (
                origin[0]
                + scaled_positions[:, 0] * lengths[0]
                + scaled_positions[:, 1] * xy
                + scaled_positions[:, 2] * xz
            )
            positions[:, 1] = (
                origin[1]
                + scaled_positions[:, 1] * lengths[1]
                + scaled_positions[:, 2] * yz
            )
            positions[:, 2] = origin[2] + scaled_positions[:, 2] * lengths[2]
        positions -= centre
        frame = DumpFrameData(
            index,
            info.timestep,
            atom_ids,
            positions.astype("f4"),
            cell_matrix.astype("f4"),
            info.periodic.copy(),
            positions_wrapped,
        )
        self._cache[index] = frame
        self._cache.move_to_end(index)
        while len(self._cache) > max(1, TRAJECTORY_CACHE_FRAMES):
            self._cache.popitem(last=False)
        return frame


def scene_from_dump_frame(frame: DumpFrameData, label: str = "LAMMPS trajectory") -> SceneData:
    """Create an atoms-only scene when no trustworthy topology file is available."""
    positions = np.asarray(frame.positions, dtype="f4")
    atom_count = len(positions)
    radii = np.full(atom_count, 0.55, dtype="f4")
    colours = np.tile(np.asarray(FALLBACK_COLOUR, dtype="f4"), (atom_count, 1))
    extent = np.linalg.norm(positions, axis=1) + radii
    radius = max(float(extent.max(initial=1.0)), 1.0)
    box_vertices = _box_line_vertices(frame.cell_matrix)
    if len(box_vertices):
        radius = max(radius, float(np.linalg.norm(box_vertices, axis=1).max(initial=1.0)))
    return SceneData(
        atom_data=_interleaved_atoms(positions, radii, colours),
        bond_data=np.empty((0, 14), dtype="f4"),
        chemical_bond_count=0,
        centre=np.zeros(3, dtype="f4"),
        radius=radius,
        label=label,
        atom_ids=np.asarray(frame.atom_ids, dtype=np.int64),
        topology_bond_indices=np.empty((0, 2), dtype=np.int32),
        cell_matrix=np.asarray(frame.cell_matrix, dtype="f4"),
        periodic=np.asarray(frame.periodic, dtype=bool),
        positions_wrapped=frame.positions_wrapped,
    )


def _build_unwrap_levels(
    atom_count: int, topology_bonds: np.ndarray | None
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Build a reusable breadth-first traversal for every bonded component."""
    if topology_bonds is None or not len(topology_bonds):
        return []
    adjacency: list[list[int]] = [[] for _ in range(atom_count)]
    for atom_a, atom_b in topology_bonds:
        a = int(atom_a)
        b = int(atom_b)
        adjacency[a].append(b)
        adjacency[b].append(a)

    visited = np.zeros(atom_count, dtype=bool)
    edges_by_depth: dict[int, tuple[list[int], list[int]]] = {}
    for root in range(atom_count):
        if visited[root] or not adjacency[root]:
            continue
        visited[root] = True
        queue = deque([(root, 0)])
        while queue:
            parent, depth = queue.popleft()
            for child in adjacency[parent]:
                if visited[child]:
                    continue
                visited[child] = True
                parents, children = edges_by_depth.setdefault(depth, ([], []))
                parents.append(parent)
                children.append(child)
                queue.append((child, depth + 1))
    return [
        (
            np.asarray(edges_by_depth[depth][0], dtype=np.int64),
            np.asarray(edges_by_depth[depth][1], dtype=np.int64),
        )
        for depth in sorted(edges_by_depth)
    ]


def _unwrap_bonded_positions(
    wrapped_positions: np.ndarray,
    unwrap_levels: list[tuple[np.ndarray, np.ndarray]],
    cell_matrix: np.ndarray,
    periodic: np.ndarray,
) -> np.ndarray:
    """Make bonded components whole using triclinic minimum-image vectors."""
    if not unwrap_levels or not np.any(periodic):
        return np.ascontiguousarray(wrapped_positions, dtype="f4")
    inverse_cell = np.linalg.inv(cell_matrix.astype("f8"))
    unwrapped = np.array(wrapped_positions, dtype="f4", copy=True, order="C")
    source = np.asarray(wrapped_positions, dtype="f8")
    for parents, children in unwrap_levels:
        delta = source[children] - source[parents]
        fractional = delta @ inverse_cell.T
        fractional[:, periodic] -= np.rint(fractional[:, periodic])
        minimum_image = fractional @ cell_matrix.astype("f8").T
        unwrapped[children] = unwrapped[parents] + minimum_image.astype("f4")
    return unwrapped


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class BackgroundWorker(QRunnable):
    """Run file parsing outside the Qt GUI thread."""

    def __init__(self, operation: Callable[[], object]):
        super().__init__()
        self.operation = operation
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.operation()
        except Exception as exc:  # Surface parser errors in the side panel.
            self.signals.error.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


def perspective(fovy_degrees: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fovy_degrees) * 0.5)
    matrix = np.zeros((4, 4), dtype="f4")
    matrix[0, 0] = f / aspect
    matrix[1, 1] = f
    matrix[2, 2] = (far + near) / (near - far)
    matrix[2, 3] = (2.0 * far * near) / (near - far)
    matrix[3, 2] = -1.0
    return matrix


def look_at(eye: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    forward = target - eye
    forward /= np.linalg.norm(forward)
    up_reference = np.array((0.0, 1.0, 0.0), dtype="f4")
    if abs(float(np.dot(forward, up_reference))) > 0.999:
        up_reference = np.array((0.0, 0.0, 1.0), dtype="f4")
    right = np.cross(forward, up_reference)
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)

    matrix = np.eye(4, dtype="f4")
    matrix[0, :3] = right
    matrix[1, :3] = up
    matrix[2, :3] = -forward
    matrix[0, 3] = -np.dot(right, eye)
    matrix[1, 3] = -np.dot(up, eye)
    matrix[2, 3] = np.dot(forward, eye)
    return matrix, right, up


ATOM_VERTEX_SHADER = r"""
    #version 330

    uniform mat4 u_proj;
    uniform mat4 u_view;
    uniform vec2 u_viewport;

    in vec3 in_position;
    in float in_radius;
    in vec3 in_colour;

    flat out vec3 v_centre_eye;
    flat out float v_radius;
    flat out vec3 v_colour;

    void main() {
        vec4 eye = u_view * vec4(in_position, 1.0);
        v_centre_eye = eye.xyz;
        v_radius = in_radius;
        v_colour = in_colour;
        gl_Position = u_proj * eye;

        float projected_diameter =
            2.0 * in_radius * u_proj[1][1] * (0.5 * u_viewport.y) /
            max(-eye.z, 1e-4);
        gl_PointSize = max(projected_diameter, 1.0);
    }
"""


def atom_fragment_shader(precise_depth: bool) -> str:
    depth_code = """
        vec3 surface_eye = v_centre_eye + vec3(uv * v_radius, nz * v_radius);
        vec4 surface_clip = u_proj * vec4(surface_eye, 1.0);
        gl_FragDepth = 0.5 * (surface_clip.z / surface_clip.w) + 0.5;
    """ if precise_depth else ""
    projection_uniform = "uniform mat4 u_proj;" if precise_depth else ""
    return f"""
        #version 330

        {projection_uniform}
        flat in vec3 v_centre_eye;
        flat in float v_radius;
        flat in vec3 v_colour;
        uniform float u_antialias;
        out vec4 f_colour;

        void main() {{
            vec2 uv = gl_PointCoord * 2.0 - 1.0;
            float r2 = dot(uv, uv);
            if (r2 > 1.0) discard;
            float coverage = 1.0;
            if (u_antialias > 0.5) {{
                float edge_width = max(fwidth(r2) * 0.75, 0.002);
                coverage = 1.0 - smoothstep(1.0 - edge_width, 1.0, r2);
            }}

            float nz = sqrt(max(1.0 - r2, 0.0));
            vec3 normal = vec3(uv, nz);
            vec3 light = normalize(vec3(-0.35, 0.55, 1.0));
            float diffuse = max(dot(normal, light), 0.0);
            float rim = pow(1.0 - nz, 2.2);
            float specular = pow(max(dot(reflect(-light, normal), vec3(0, 0, 1)), 0.0), 32.0);
            vec3 colour = v_colour * (0.20 + 0.76 * diffuse) + 0.20 * rim + 0.32 * specular;
            f_colour = vec4(colour, coverage);
            {depth_code}
        }}
    """


BOND_VERTEX_SHADER = r"""
    #version 330

    uniform mat4 u_proj;
    uniform mat4 u_view;
    uniform vec2 u_viewport;

    in vec2 in_corner;
    in vec3 in_start;
    in vec3 in_end;
    in float in_radius;
    in vec3 in_start_colour;
    in vec3 in_end_colour;
    in float in_dash_count;

    flat out vec2 v_start_px;
    flat out vec2 v_end_px;
    flat out vec3 v_start_eye;
    flat out vec3 v_end_eye;
    flat out float v_start_radius_px;
    flat out float v_end_radius_px;
    flat out float v_world_radius;
    flat out vec3 v_start_colour;
    flat out vec3 v_end_colour;
    flat out float v_dash_count;

    void main() {
        vec4 start_eye4 = u_view * vec4(in_start, 1.0);
        vec4 end_eye4 = u_view * vec4(in_end, 1.0);
        vec4 start_clip = u_proj * start_eye4;
        vec4 end_clip = u_proj * end_eye4;

        vec2 start_px = (start_clip.xy / start_clip.w * 0.5 + 0.5) * u_viewport;
        vec2 end_px = (end_clip.xy / end_clip.w * 0.5 + 0.5) * u_viewport;
        float start_r = in_radius * u_proj[1][1] * (0.5 * u_viewport.y) /
                        max(-start_eye4.z, 1e-4);
        float end_r = in_radius * u_proj[1][1] * (0.5 * u_viewport.y) /
                      max(-end_eye4.z, 1e-4);

        vec2 axis = end_px - start_px;
        float axis_length = max(length(axis), 1e-4);
        vec2 direction = axis / axis_length;
        vec2 perpendicular = vec2(-direction.y, direction.x);
        float t = in_corner.x;
        float side = in_corner.y;
        float radius_px = mix(start_r, end_r, t);
        vec2 pixel_position = mix(start_px, end_px, t)
                            + perpendicular * side * radius_px
                            + direction * mix(-start_r, end_r, t);

        vec4 clip = mix(start_clip, end_clip, t);
        vec2 ndc = pixel_position / u_viewport * 2.0 - 1.0;
        gl_Position = vec4(ndc * clip.w, clip.z, clip.w);

        v_start_px = start_px;
        v_end_px = end_px;
        v_start_eye = start_eye4.xyz;
        v_end_eye = end_eye4.xyz;
        v_start_radius_px = start_r;
        v_end_radius_px = end_r;
        v_world_radius = in_radius;
        v_start_colour = in_start_colour;
        v_end_colour = in_end_colour;
        v_dash_count = in_dash_count;
    }
"""


BOX_VERTEX_SHADER = r"""
    #version 330
    uniform mat4 u_proj;
    uniform mat4 u_view;
    in vec3 in_position;
    void main() {
        gl_Position = u_proj * u_view * vec4(in_position, 1.0);
    }
"""

BOX_FRAGMENT_SHADER = r"""
    #version 330
    out vec4 f_colour;
    void main() {
        f_colour = vec4(0.0, 0.0, 0.0, 1.0);
    }
"""


def _box_line_vertices(cell_matrix: np.ndarray | None) -> np.ndarray:
    if cell_matrix is None:
        return np.empty((0, 3), dtype="f4")
    fractional = np.asarray(
        [
            (-0.5, -0.5, -0.5),
            (0.5, -0.5, -0.5),
            (-0.5, 0.5, -0.5),
            (0.5, 0.5, -0.5),
            (-0.5, -0.5, 0.5),
            (0.5, -0.5, 0.5),
            (-0.5, 0.5, 0.5),
            (0.5, 0.5, 0.5),
        ],
        dtype="f4",
    )
    corners = fractional @ np.asarray(cell_matrix, dtype="f4").T
    edges = (
        (0, 1), (0, 2), (1, 3), (2, 3),
        (4, 5), (4, 6), (5, 7), (6, 7),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )
    return np.asarray(
        [corners[index] for edge in edges for index in edge], dtype="f4"
    )


def bond_fragment_shader(precise_depth: bool) -> str:
    depth_code = """
        vec3 centre_eye = mix(v_start_eye, v_end_eye, t);
        centre_eye.z += v_world_radius * normal.z;
        vec4 surface_clip = u_proj * vec4(centre_eye, 1.0);
        gl_FragDepth = 0.5 * (surface_clip.z / surface_clip.w) + 0.5;
    """ if precise_depth else ""
    projection_uniform = "uniform mat4 u_proj;" if precise_depth else ""
    return f"""
        #version 330

        {projection_uniform}
        flat in vec2 v_start_px;
        flat in vec2 v_end_px;
        flat in vec3 v_start_eye;
        flat in vec3 v_end_eye;
        flat in float v_start_radius_px;
        flat in float v_end_radius_px;
        flat in float v_world_radius;
        flat in vec3 v_start_colour;
        flat in vec3 v_end_colour;
        flat in float v_dash_count;
        uniform float u_antialias;
        out vec4 f_colour;

        void main() {{
            vec2 segment = v_end_px - v_start_px;
            float length_squared = max(dot(segment, segment), 1e-6);
            float t = clamp(dot(gl_FragCoord.xy - v_start_px, segment) / length_squared, 0.0, 1.0);
            if (v_dash_count > 0.0 && fract(t * v_dash_count) > 0.62) discard;
            vec2 nearest = mix(v_start_px, v_end_px, t);
            float radius_px = max(mix(v_start_radius_px, v_end_radius_px, t), 0.5);
            vec2 offset = (gl_FragCoord.xy - nearest) / radius_px;
            float r2 = dot(offset, offset);
            if (r2 > 1.0) discard;
            float coverage = 1.0;
            if (u_antialias > 0.5) {{
                float edge_width = max(fwidth(r2) * 0.75, 0.002);
                coverage = 1.0 - smoothstep(1.0 - edge_width, 1.0, r2);
            }}

            vec3 normal = vec3(offset, sqrt(max(1.0 - r2, 0.0)));
            vec3 light = normalize(vec3(-0.35, 0.55, 1.0));
            float diffuse = max(dot(normal, light), 0.0);
            float specular = pow(max(dot(reflect(-light, normal), vec3(0, 0, 1)), 0.0), 24.0);
            vec3 base = mix(v_start_colour, v_end_colour, t);
            f_colour = vec4(
                base * (0.24 + 0.72 * diffuse) + 0.24 * specular,
                coverage
            );
            {depth_code}
        }}
    """


class MolecularViewerWidget(QOpenGLWidget):
    """ModernGL renderer embedded as a normal PySide6 widget."""

    def __init__(self, parent=None, scene: SceneData | None = None, embedded: bool = False):
        super().__init__(parent)
        self.embedded = embedded
        surface_format = self.format()
        surface_format.setSamples(IDLE_ANTIALIAS_SAMPLES)
        self.setFormat(surface_format)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)

        self._fast_rendering = False
        self._antialias_timer = QTimer(self)
        self._antialias_timer.setSingleShot(True)
        self._antialias_timer.setInterval(IDLE_ANTIALIAS_DELAY_MS)
        self._antialias_timer.timeout.connect(self._restore_idle_antialiasing)

        if scene is not None:
            self.scene = scene
        elif BENCHMARK_ATOMS:
            self.scene = benchmark_scene(
                BENCHMARK_ATOMS, BENCHMARK_EXTENT, EMBEDDING_SEED
            )
        else:
            self.scene = scene_from_smiles(
                SMILES, ATOM_SCALE, BOND_RADIUS, BOND_SEPARATION, EMBEDDING_SEED
            )

        self.atom_count = len(self.scene.atom_data)
        self.bond_count = self.scene.chemical_bond_count
        self.bond_primitive_count = len(self.scene.bond_data)
        self.precise_depth = not FAST_DEPTH and not bool(BENCHMARK_ATOMS)
        self.pbc_enabled = True
        self.atoms_visible = True
        self.bonds_visible = True
        self.box_visible = True
        self._raw_positions = np.ascontiguousarray(
            self.scene.atom_data[:, :3], dtype="f4"
        )
        self._cell_matrix = self.scene.cell_matrix
        self._periodic = self.scene.periodic
        self._positions_wrapped = self.scene.positions_wrapped
        self._unwrap_levels = _build_unwrap_levels(
            self.atom_count, self.scene.topology_bond_indices
        )

        self.ctx = None
        self.qt_framebuffer = None
        self.atom_program = None
        self.bond_program = None
        self.box_program = None
        self.atom_position_vbo = None
        self.atom_visual_vbo = None
        self.atom_vao = None
        self.quad_vbo = None
        self.bond_vbo = None
        self.bond_vao = None
        self.box_vbo = None
        self.box_vao = None
        self.box_vertex_count = 0
        self._trajectory_source_ids = None
        self._trajectory_target_indices = None

        self.target = self.scene.centre.copy()
        self.yaw = math.radians(35.0)
        self.pitch = math.radians(22.0)
        self.fit_distance = self.scene.radius / math.tan(math.radians(45.0) * 0.5) * 1.18
        self.distance = max(self.fit_distance, 0.5)
        self.min_distance = max(self.scene.radius * 0.08, 0.03)
        self.max_distance = max(self.scene.radius * 250.0, 100.0)
        self.camera_right = np.array((1.0, 0.0, 0.0), dtype="f4")
        self.camera_up = np.array((0.0, 1.0, 0.0), dtype="f4")
        self._last_mouse_position = None
        self._fps_started = time.perf_counter()
        self._fps_frames = 0

        mode = "accurate depth" if self.precise_depth else "fast depth"
        print(
            f"Loaded {self.scene.label}: {self.atom_count:,} atoms, "
            f"{self.bond_count:,} bonds / {self.bond_primitive_count:,} bond impostors "
            f"({mode})\n"
            "Controls: left-drag orbit | right/middle-drag pan | wheel zoom | F reset"
        )

    def initializeGL(self):
        """Attach ModernGL to Qt's current OpenGL context and upload GPU data."""
        self.ctx = moderngl.create_context(require=330)
        self.ctx.gc_mode = "auto"
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.PROGRAM_POINT_SIZE)
        self.ctx.depth_func = "<="

        self.atom_program = self.ctx.program(
            vertex_shader=ATOM_VERTEX_SHADER,
            fragment_shader=atom_fragment_shader(self.precise_depth),
        )
        self.bond_program = self.ctx.program(
            vertex_shader=BOND_VERTEX_SHADER,
            fragment_shader=bond_fragment_shader(self.precise_depth),
        )
        self.box_program = self.ctx.program(
            vertex_shader=BOX_VERTEX_SHADER,
            fragment_shader=BOX_FRAGMENT_SHADER,
        )
        # One four-vertex strip is reused for every bond instance and scene.
        quad = np.asarray(((0, -1), (0, 1), (1, -1), (1, 1)), dtype="f4")
        self.quad_vbo = self.ctx.buffer(quad)
        self._create_scene_buffers()
        qt_context = self.context()
        if qt_context is not None:
            qt_context.aboutToBeDestroyed.connect(self.cleanup)

    def _create_scene_buffers(self):
        positions = np.ascontiguousarray(self.scene.atom_data[:, :3], dtype="f4")
        visuals = np.ascontiguousarray(self.scene.atom_data[:, 3:7], dtype="f4")
        self.atom_position_vbo = (
            self.ctx.buffer(positions, dynamic=True)
            if positions.nbytes
            else self.ctx.buffer(reserve=12, dynamic=True)
        )
        self.atom_visual_vbo = (
            self.ctx.buffer(visuals) if visuals.nbytes else self.ctx.buffer(reserve=16)
        )
        self.atom_vao = self.ctx.vertex_array(
            self.atom_program,
            [
                (self.atom_position_vbo, "3f", "in_position"),
                (self.atom_visual_vbo, "1f 3f", "in_radius", "in_colour"),
            ],
        )
        self.bond_vbo = (
            self.ctx.buffer(
                self.scene.bond_data,
                dynamic=self.scene.bond_indices is not None,
            )
            if self.bond_primitive_count
            else self.ctx.buffer(reserve=14 * 4)
        )
        self.bond_vao = self.ctx.vertex_array(
            self.bond_program,
            [
                (self.quad_vbo, "2f", "in_corner"),
                (
                    self.bond_vbo,
                    "3f 3f 1f 3f 3f 1f /i",
                    "in_start",
                    "in_end",
                    "in_radius",
                    "in_start_colour",
                    "in_end_colour",
                    "in_dash_count",
                ),
            ],
        )
        self._create_box_buffer()

    def _create_box_buffer(self):
        box_vertices = _box_line_vertices(self.scene.cell_matrix)
        self.box_vertex_count = len(box_vertices)
        self.box_vbo = (
            self.ctx.buffer(box_vertices)
            if box_vertices.nbytes
            else self.ctx.buffer(reserve=12)
        )
        self.box_vao = self.ctx.vertex_array(
            self.box_program, [(self.box_vbo, "3f", "in_position")]
        )

    def _refresh_box_buffer(self):
        if self.ctx is None:
            return
        self.makeCurrent()
        for name in ("box_vao", "box_vbo"):
            resource = getattr(self, name, None)
            if resource is not None:
                resource.release()
                setattr(self, name, None)
        self._create_box_buffer()
        self.doneCurrent()

    def _release_scene_buffers(self):
        for name in (
            "atom_vao",
            "bond_vao",
            "atom_position_vbo",
            "atom_visual_vbo",
            "bond_vbo",
            "box_vao",
            "box_vbo",
        ):
            resource = getattr(self, name, None)
            if resource is not None:
                resource.release()
                setattr(self, name, None)

    def _reset_camera(self):
        self.target = self.scene.centre.copy()
        self.fit_distance = (
            self.scene.radius / math.tan(math.radians(45.0) * 0.5) * 1.18
        )
        self.distance = max(self.fit_distance, 0.5)
        self.min_distance = max(self.scene.radius * 0.08, 0.03)
        self.max_distance = max(self.scene.radius * 250.0, 100.0)
        self.yaw = math.radians(35.0)
        self.pitch = math.radians(22.0)

    def reset_camera(self):
        self._reset_camera()
        self.update()

    def set_camera_view(self, view: str):
        """Fit the scene using one of the named, reproducible camera views."""
        self.target = self.scene.centre.copy()
        self.distance = max(self.fit_distance, 0.5)
        angles = {
            "isometric": (math.radians(35.0), math.radians(22.0)),
            "front": (0.0, -math.pi * 0.5),      # view from -Y; Z remains up
            "side": (0.0, 0.0),                 # look along +X
            "top": (math.pi * 0.5, 0.0),        # look along +Z
        }
        try:
            self.yaw, self.pitch = angles[view.strip().lower()]
        except KeyError as exc:
            raise ValueError(f"Unknown camera view: {view}") from exc
        self._fast_rendering = False
        self._antialias_timer.stop()
        self.update()

    def set_atoms_visible(self, visible: bool):
        self.atoms_visible = bool(visible)
        self.update()

    def set_bonds_visible(self, visible: bool):
        self.bonds_visible = bool(visible)
        self.update()

    def set_box_visible(self, visible: bool):
        self.box_visible = bool(visible)
        self.update()

    def save_view(self, path: str | Path) -> bool:
        """Save the current antialiased framebuffer exactly as shown."""
        self._fast_rendering = False
        self._antialias_timer.stop()
        self.repaint()
        return bool(self.grabFramebuffer().save(str(path), "PNG"))

    def set_scene(self, scene: SceneData):
        """Replace the displayed system and rebuild only scene-dependent buffers."""
        self.scene = scene
        self.atom_count = len(scene.atom_data)
        self.bond_count = scene.chemical_bond_count
        self.bond_primitive_count = len(scene.bond_data)
        self._raw_positions = np.ascontiguousarray(scene.atom_data[:, :3], dtype="f4")
        self._cell_matrix = scene.cell_matrix
        self._periodic = scene.periodic
        self._positions_wrapped = scene.positions_wrapped
        self._unwrap_levels = _build_unwrap_levels(
            self.atom_count, scene.topology_bond_indices
        )
        self._trajectory_source_ids = None
        self._trajectory_target_indices = None
        self._apply_raw_positions(upload=False)
        self._reset_camera()
        if self.ctx is not None:
            self.makeCurrent()
            self._release_scene_buffers()
            self._create_scene_buffers()
            self.doneCurrent()
        self.update()

    def set_pbc_enabled(self, enabled: bool):
        self.pbc_enabled = bool(enabled)
        self._apply_raw_positions(upload=True)

    def _apply_raw_positions(self, upload: bool):
        if (
            self.pbc_enabled
            and self._positions_wrapped
            and self._cell_matrix is not None
            and self._periodic is not None
        ):
            positions = _unwrap_bonded_positions(
                self._raw_positions,
                self._unwrap_levels,
                self._cell_matrix,
                self._periodic,
            )
        else:
            positions = np.ascontiguousarray(self._raw_positions, dtype="f4")

        self.scene.atom_data[:, :3] = positions
        if self.scene.bond_indices is not None and self.bond_primitive_count:
            offsets = self.scene.bond_offsets
            if offsets is None:
                offsets = np.zeros((self.bond_primitive_count, 3), dtype="f4")
            self.scene.bond_data[:, 0:3] = (
                positions[self.scene.bond_indices[:, 0]] + offsets
            )
            self.scene.bond_data[:, 3:6] = (
                positions[self.scene.bond_indices[:, 1]] + offsets
            )

        if upload and self.ctx is not None:
            self.makeCurrent()
            self.atom_position_vbo.write(positions)
            if self.bond_primitive_count:
                self.bond_vbo.write(self.scene.bond_data)
            self.doneCurrent()
        self.update()

    def set_trajectory_frame(self, frame: DumpFrameData):
        """Map one dump frame by atom ID and upload positions to the GPU."""
        self._begin_fast_rendering()
        if self.scene.atom_ids is None:
            raise ValueError("Load a LAMMPS structure data file before a trajectory")
        if len(frame.atom_ids) != self.atom_count:
            raise ValueError(
                f"Frame has {len(frame.atom_ids):,} atoms; structure has "
                f"{self.atom_count:,}"
            )

        if np.array_equal(frame.atom_ids, self.scene.atom_ids):
            positions = frame.positions
        else:
            if (
                self._trajectory_source_ids is None
                or not np.array_equal(frame.atom_ids, self._trajectory_source_ids)
            ):
                id_to_index = {
                    int(atom_id): index
                    for index, atom_id in enumerate(self.scene.atom_ids)
                }
                try:
                    target_indices = np.fromiter(
                        (id_to_index[int(atom_id)] for atom_id in frame.atom_ids),
                        dtype=np.int64,
                        count=self.atom_count,
                    )
                except KeyError as exc:
                    raise ValueError(
                        f"Trajectory contains atom ID {exc.args[0]} absent from structure"
                    ) from exc
                if len(np.unique(target_indices)) != self.atom_count:
                    raise ValueError("Trajectory contains duplicate atom IDs")
                self._trajectory_source_ids = frame.atom_ids.copy()
                self._trajectory_target_indices = target_indices
            positions = np.empty_like(frame.positions)
            positions[self._trajectory_target_indices] = frame.positions

        self._raw_positions = np.ascontiguousarray(positions, dtype="f4")
        self._cell_matrix = frame.cell_matrix
        self._periodic = frame.periodic
        self._positions_wrapped = frame.positions_wrapped
        self.scene.cell_matrix = frame.cell_matrix
        self.scene.periodic = frame.periodic
        self.scene.positions_wrapped = frame.positions_wrapped
        atom_radii = self.scene.atom_data[:, 3]
        extent = np.linalg.norm(self._raw_positions, axis=1) + atom_radii
        radius = max(float(extent.max(initial=1.0)), 1.0)
        box_vertices = _box_line_vertices(frame.cell_matrix)
        if len(box_vertices):
            radius = max(
                radius,
                float(np.linalg.norm(box_vertices, axis=1).max(initial=1.0)),
            )
        self.scene.radius = radius
        self.min_distance = max(radius * 0.08, 0.03)
        self.max_distance = max(radius * 250.0, 100.0)
        self._apply_raw_positions(upload=True)
        self._refresh_box_buffer()

    def cleanup(self):
        """Release GL objects while Qt's context can still be made current."""
        if self.ctx is None:
            return
        self.makeCurrent()
        self._release_scene_buffers()
        for name in ("quad_vbo", "atom_program", "bond_program", "box_program"):
            resource = getattr(self, name, None)
            if resource is not None:
                resource.release()
                setattr(self, name, None)
        self.qt_framebuffer = None
        self.ctx = None
        self.doneCurrent()

    def _camera(self) -> tuple[np.ndarray, np.ndarray]:
        cos_pitch = math.cos(self.pitch)
        eye = self.target + self.distance * np.asarray(
            (
                cos_pitch * math.cos(self.yaw),
                math.sin(self.pitch),
                cos_pitch * math.sin(self.yaw),
            ),
            dtype="f4",
        )
        view, self.camera_right, self.camera_up = look_at(eye, self.target)
        scene_distance = float(np.linalg.norm(eye - self.scene.centre))
        near = max(scene_distance - self.scene.radius * 1.5, self.distance * 0.001, 0.001)
        far = max(scene_distance + self.scene.radius * 2.5, near + 10.0)
        framebuffer_width, framebuffer_height = self._framebuffer_size()
        aspect = framebuffer_width / max(float(framebuffer_height), 1.0)
        projection = perspective(45.0, max(aspect, 1e-5), near, far)
        return view, projection

    def _framebuffer_size(self) -> tuple[int, int]:
        pixel_ratio = float(self.devicePixelRatioF())
        return (
            max(1, round(self.width() * pixel_ratio)),
            max(1, round(self.height() * pixel_ratio)),
        )

    @staticmethod
    def _write_common_uniforms(program, view, projection, viewport, antialias):
        # NumPy stores rows contiguously; transpose for OpenGL column-major upload.
        program["u_view"].write(view.T.astype("f4", copy=False).tobytes())
        program["u_proj"].write(projection.T.astype("f4", copy=False).tobytes())
        program["u_viewport"].value = viewport
        program["u_antialias"].value = 1.0 if antialias else 0.0

    def _begin_fast_rendering(self):
        self._fast_rendering = True
        self._antialias_timer.start()

    @Slot()
    def _restore_idle_antialiasing(self):
        if not self._fast_rendering:
            return
        self._fast_rendering = False
        self.update()

    def paintGL(self):
        if self.ctx is None:
            return
        # Register Qt's non-zero backing FBO with ModernGL. Calling use() is
        # important: a raw glBindFramebuffer call would leave ModernGL's own
        # active-framebuffer cache pointing at framebuffer 0.
        qt_framebuffer_id = int(self.defaultFramebufferObject())
        if (
            self.qt_framebuffer is None
            or self.qt_framebuffer.glo != qt_framebuffer_id
        ):
            self.qt_framebuffer = self.ctx.detect_framebuffer(qt_framebuffer_id)
        self.qt_framebuffer.use()

        framebuffer_width, framebuffer_height = self._framebuffer_size()
        self.qt_framebuffer.viewport = (0, 0, framebuffer_width, framebuffer_height)
        self.qt_framebuffer.color_mask = (True, True, True, True)
        self.qt_framebuffer.depth_mask = True

        # Qt uses the context between frames. Reset all relevant raster state,
        # including a possible composition scissor that can reject every pixel.
        antialias = not self._fast_rendering
        render_state = moderngl.DEPTH_TEST | moderngl.PROGRAM_POINT_SIZE
        if antialias:
            render_state |= getattr(moderngl, "MULTISAMPLE", 0)
        self.ctx.enable_only(render_state)
        # Convert the shader's edge alpha into multisample coverage instead of
        # blending translucent, depth-writing fragments against white. This
        # avoids pale outlines where atoms and bonds overlap while retaining a
        # smooth idle image.
        gl = QOpenGLContext.currentContext().functions()
        if antialias:
            gl.glEnable(GL_SAMPLE_ALPHA_TO_COVERAGE)
        else:
            gl.glDisable(GL_SAMPLE_ALPHA_TO_COVERAGE)
        self.ctx.scissor = None
        self.ctx.depth_func = "<="
        self.qt_framebuffer.clear(*BACKGROUND)
        view, projection = self._camera()
        viewport = (float(framebuffer_width), float(framebuffer_height))

        if self.box_visible and self.box_vertex_count:
            self.box_program["u_view"].write(view.T.astype("f4", copy=False).tobytes())
            self.box_program["u_proj"].write(projection.T.astype("f4", copy=False).tobytes())
            self.box_vao.render(mode=moderngl.LINES, vertices=self.box_vertex_count)

        if self.bonds_visible and self.bond_primitive_count:
            self._write_common_uniforms(
                self.bond_program, view, projection, viewport, antialias
            )
            self.bond_vao.render(
                mode=moderngl.TRIANGLE_STRIP,
                vertices=4,
                instances=self.bond_primitive_count,
            )

        if self.atoms_visible and self.atom_count:
            self._write_common_uniforms(
                self.atom_program, view, projection, viewport, antialias
            )
            self.atom_vao.render(mode=moderngl.POINTS, vertices=self.atom_count)

        self._fps_frames += 1
        now = time.perf_counter()
        elapsed = now - self._fps_started
        if elapsed >= 1.0:
            fps = self._fps_frames / elapsed
            if not self.embedded:
                self.window().setWindowTitle(
                    f"Molecular Viewer | {self.atom_count:,} atoms | "
                    f"{self.bond_count:,} bonds | {fps:.0f} FPS"
                )
            self._fps_started = now
            self._fps_frames = 0

    def resizeGL(self, width: int, height: int):
        # Qt recreates the backing framebuffer on resize. Force re-detection in
        # paintGL even if the driver happens to recycle the same numeric ID.
        self.qt_framebuffer = None
        self._begin_fast_rendering()
        if self.ctx is not None:
            framebuffer_width, framebuffer_height = self._framebuffer_size()
            self.ctx.viewport = (0, 0, framebuffer_width, framebuffer_height)

    def mousePressEvent(self, event: QMouseEvent):
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._begin_fast_rendering()
        self._last_mouse_position = event.position()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._last_mouse_position = None
        self._antialias_timer.start()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        position = event.position()
        if self._last_mouse_position is None:
            self._last_mouse_position = position
            return
        delta = position - self._last_mouse_position
        self._last_mouse_position = position
        dx = float(delta.x())
        dy = float(delta.y())
        buttons = event.buttons()
        if buttons & Qt.MouseButton.LeftButton:
            self._begin_fast_rendering()
            self.yaw -= dx * 0.006
            self.pitch = float(
                np.clip(self.pitch + dy * 0.006, -math.pi * 0.495, math.pi * 0.495)
            )
        elif buttons & (Qt.MouseButton.RightButton | Qt.MouseButton.MiddleButton):
            self._begin_fast_rendering()
            world_per_pixel = 2.0 * self.distance * math.tan(math.radians(22.5))
            world_per_pixel /= max(float(self.height()), 1.0)
            self.target += (
                -self.camera_right * dx + self.camera_up * dy
            ) * world_per_pixel
        self.update()
        event.accept()

    def wheelEvent(self, event: QWheelEvent):
        self._begin_fast_rendering()
        steps = float(event.angleDelta().y()) / 120.0
        self.distance *= math.exp(-steps * 0.12)
        self.distance = float(np.clip(self.distance, self.min_distance, self.max_distance))
        self.update()
        event.accept()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F:
            self._reset_camera()
            self.update()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape and not self.embedded:
            self.window().close()
            event.accept()
        else:
            super().keyPressEvent(event)


class MolecularViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Molecular Viewer")
        self.resize(1600, 900)

        self.thread_pool = QThreadPool(self)
        self._workers: set[BackgroundWorker] = set()
        self.trajectory: LammpsDumpTrajectory | None = None
        self._trajectory_generation = 0
        self._requested_frame = -1
        self._frame_worker_active = False

        self.viewer = MolecularViewerWidget(self)
        panel = self._create_side_panel()
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel)
        layout.addWidget(self.viewer, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage(
            "Left drag: orbit   |   Right/middle drag: pan   |   Wheel: zoom   |   F: reset"
        )

    def _create_side_panel(self) -> QWidget:
        panel = QWidget(self)
        panel.setFixedWidth(310)
        panel.setStyleSheet(
            "QWidget { background: #171b24; color: #e8ebf1; }"
            "QPushButton { background: #2b3445; border: 1px solid #465169; "
            "padding: 9px; border-radius: 4px; text-align: left; }"
            "QPushButton:hover { background: #354158; }"
            "QPushButton:disabled { color: #747b89; background: #202530; }"
            "QCheckBox { spacing: 8px; padding: 4px 0; }"
            "QSlider::groove:horizontal { height: 5px; background: #343c4c; }"
            "QSlider::handle:horizontal { width: 15px; margin: -5px 0; "
            "border-radius: 7px; background: #73a7ff; }"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 20, 18, 18)
        layout.setSpacing(10)

        title = QLabel("LAMMPS system")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        structure_heading = QLabel("TOPOLOGY / STRUCTURE")
        structure_heading.setStyleSheet("color: #8f9aaf; font-size: 10px;")
        layout.addSpacing(8)
        layout.addWidget(structure_heading)
        self.structure_button = QPushButton("Load structure.data…")
        self.structure_button.clicked.connect(self._choose_structure)
        layout.addWidget(self.structure_button)
        self.structure_label = QLabel("No structure loaded")
        self.structure_label.setWordWrap(True)
        self.structure_label.setStyleSheet("color: #aab2c2; font-size: 11px;")
        layout.addWidget(self.structure_label)
        self.pbc_checkbox = QCheckBox("Make molecules whole (PBC)")
        self.pbc_checkbox.setChecked(True)
        self.pbc_checkbox.setToolTip(
            "Use minimum-image bond vectors to unwrap bonded components across "
            "periodic box boundaries."
        )
        self.pbc_checkbox.toggled.connect(self.viewer.set_pbc_enabled)
        layout.addWidget(self.pbc_checkbox)

        trajectory_heading = QLabel("TRAJECTORY")
        trajectory_heading.setStyleSheet("color: #8f9aaf; font-size: 10px;")
        layout.addSpacing(14)
        layout.addWidget(trajectory_heading)
        self.trajectory_button = QPushButton("Load LAMMPS dump…")
        self.trajectory_button.clicked.connect(self._choose_trajectory)
        layout.addWidget(self.trajectory_button)
        self.trajectory_label = QLabel("No trajectory loaded")
        self.trajectory_label.setWordWrap(True)
        self.trajectory_label.setStyleSheet("color: #aab2c2; font-size: 11px;")
        layout.addWidget(self.trajectory_label)

        layout.addSpacing(14)
        self.frame_label = QLabel("Frame — / —")
        self.frame_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.frame_label)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self._queue_frame)
        layout.addWidget(self.frame_slider)

        self.load_status = QLabel("")
        self.load_status.setWordWrap(True)
        self.load_status.setStyleSheet("color: #73a7ff; font-size: 11px;")
        layout.addWidget(self.load_status)
        layout.addStretch(1)

        note = QLabel(
            "The data file supplies atom IDs, types, masses and bonds. "
            "Trajectory frames are indexed and loaded on demand."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7f899d; font-size: 10px;")
        layout.addWidget(note)
        return panel

    def _start_worker(
        self,
        operation: Callable[[], object],
        on_result: Callable[[object], None],
        on_error: Callable[[str], None] | None = None,
    ):
        worker = BackgroundWorker(operation)
        self._workers.add(worker)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error or self._show_error)
        worker.signals.finished.connect(lambda: self._workers.discard(worker))
        self.thread_pool.start(worker)

    def _show_error(self, message: str):
        self.load_status.setText("Load failed")
        QMessageBox.critical(self, "LAMMPS load error", message)

    def _choose_structure(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open LAMMPS structure/data file",
            str(Path.cwd()),
            "LAMMPS data files (*.data *.lmp data.*);;All files (*)",
        )
        if not path:
            return
        self.structure_button.setEnabled(False)
        self.load_status.setText("Reading structure and topology…")
        self._start_worker(
            lambda selected_path=path: scene_from_lammps_data(selected_path),
            lambda scene, selected_path=path: self._structure_loaded(
                selected_path, scene
            ),
            self._structure_failed,
        )

    def _structure_loaded(self, path: str, scene: SceneData):
        self.structure_button.setEnabled(True)
        try:
            self.viewer.set_scene(scene)
        except Exception as exc:
            self._show_error(f"OpenGL upload failed: {exc}")
            return
        self.structure_label.setText(
            f"{Path(path).name}\n{len(scene.atom_data):,} atoms · "
            f"{scene.chemical_bond_count:,} bonds"
        )
        self._clear_trajectory()
        self.load_status.setText("Structure loaded")

    def _structure_failed(self, message: str):
        self.structure_button.setEnabled(True)
        self._show_error(message)

    def _choose_trajectory(self):
        if self.viewer.scene.atom_ids is None:
            QMessageBox.information(
                self,
                "Load structure first",
                "Load the matching LAMMPS structure/data file before its trajectory.",
            )
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open LAMMPS dump trajectory",
            str(Path.cwd()),
            "LAMMPS dump files (*.dump *.lammpstrj *.traj);;All files (*)",
        )
        if not path:
            return
        self.trajectory_button.setEnabled(False)
        self.frame_slider.setEnabled(False)
        self.load_status.setText("Indexing trajectory…")
        self._start_worker(
            lambda selected_path=path: LammpsDumpTrajectory(selected_path).build_index(),
            self._trajectory_loaded,
            self._trajectory_failed,
        )

    def _trajectory_loaded(self, trajectory: LammpsDumpTrajectory):
        self.trajectory_button.setEnabled(True)
        expected_atoms = self.viewer.atom_count
        mismatched = next(
            (
                frame.atom_count
                for frame in trajectory.frames
                if frame.atom_count != expected_atoms
            ),
            None,
        )
        if mismatched is not None:
            self._show_error(
                f"Trajectory contains a {mismatched:,}-atom frame, but the "
                f"structure contains {expected_atoms:,} atoms."
            )
            return
        self.trajectory = trajectory
        self._trajectory_generation += 1
        frame_count = len(trajectory.frames)
        self.trajectory_label.setText(
            f"{trajectory.path.name}\n{frame_count:,} frames"
        )
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, frame_count - 1)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(True)
        self.load_status.setText("Trajectory indexed")
        self._queue_frame(0)

    def _trajectory_failed(self, message: str):
        self.trajectory_button.setEnabled(True)
        self._show_error(message)

    def _clear_trajectory(self):
        self._trajectory_generation += 1
        self.trajectory = None
        self._requested_frame = -1
        self._frame_worker_active = False
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, 0)
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self.frame_slider.setEnabled(False)
        self.frame_label.setText("Frame — / —")
        self.trajectory_label.setText("No trajectory loaded")

    def _queue_frame(self, index: int):
        if self.trajectory is None:
            return
        self._requested_frame = int(index)
        info = self.trajectory.frames[index]
        self.frame_label.setText(
            f"Frame {index + 1:,} / {len(self.trajectory.frames):,}\n"
            f"Timestep {info.timestep:,}"
        )
        if not self._frame_worker_active:
            self._start_frame_load()

    def _start_frame_load(self):
        if (
            self.trajectory is None
            or self._requested_frame < 0
            or self._frame_worker_active
        ):
            return
        index = self._requested_frame
        trajectory = self.trajectory
        generation = self._trajectory_generation
        self._frame_worker_active = True
        self._start_worker(
            lambda: (generation, trajectory, trajectory.load_frame(index)),
            self._frame_loaded,
            self._frame_failed,
        )

    def _frame_loaded(self, payload: tuple[int, LammpsDumpTrajectory, DumpFrameData]):
        generation, source_trajectory, frame = payload
        self._frame_worker_active = False
        if (
            self.trajectory is None
            or generation != self._trajectory_generation
            or source_trajectory is not self.trajectory
        ):
            if self.trajectory is not None and self._requested_frame >= 0:
                self._start_frame_load()
            return
        try:
            self.viewer.set_trajectory_frame(frame)
        except Exception as exc:
            self._show_error(str(exc))
            return
        self.load_status.setText(
            f"Frame {frame.index + 1:,} · timestep {frame.timestep:,}"
        )
        if frame.index != self._requested_frame:
            self._start_frame_load()

    def _frame_failed(self, message: str):
        self._frame_worker_active = False
        self._show_error(message)

    def closeEvent(self, event: QCloseEvent):
        self.thread_pool.clear()
        self.viewer.cleanup()
        super().closeEvent(event)


def configure_opengl():
    """Request the same OpenGL 3.3 core context on every Qt platform."""
    surface_format = QSurfaceFormat()
    surface_format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    surface_format.setVersion(3, 3)
    surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    surface_format.setDepthBufferSize(24)
    surface_format.setSamples(IDLE_ANTIALIAS_SAMPLES)
    surface_format.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(surface_format)


def empty_scene(label: str = "No structure loaded") -> SceneData:
    """Create a safe zero-geometry scene for embedding before Stage 2 runs."""
    return SceneData(
        atom_data=np.empty((0, 7), dtype="f4"),
        bond_data=np.empty((0, 14), dtype="f4"),
        chemical_bond_count=0,
        centre=np.zeros(3, dtype="f4"),
        radius=1.0,
        label=label,
    )


if __name__ == "__main__":
    configure_opengl()
    application = QApplication([])
    window = MolecularViewerWindow()
    window.show()
    raise SystemExit(application.exec())
