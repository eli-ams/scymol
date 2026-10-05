from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class MoleculeSpec:
    id: str = field(default_factory=new_id)
    name: str = "Molecule"
    smiles: str = "CCO"
    count: int = 1
    formula: str = ""
    bond_order_status: str = ""


@dataclass
class MergeSource:
    id: str = field(default_factory=new_id)
    path: str = ""
    shift_x: float = 0.0
    shift_y: float = 0.0
    shift_z: float = 0.0


@dataclass
class StructureSettings:
    source_mode: str = "generate"
    forcefield: str = "Gaff2"
    charges: str = "gasteiger"
    box_padding_angstrom: float = 8.0
    boundary: str = "p p p"
    atom_style: str = "full"


@dataclass
class ProtocolNode:
    id: str = field(default_factory=new_id)
    kind: str = "NVT"
    name: str = "NVT"
    parameters: dict[str, Any] = field(default_factory=dict)
    loop_enabled: bool = False
    loop_values: str = "1 2 3 4"
    loop_expressions: dict[str, str] = field(default_factory=dict)
    x: float = 0.0
    y: float = 0.0


@dataclass
class ProtocolEdge:
    source: str
    target: str


@dataclass
class ProtocolGraph:
    nodes: list[ProtocolNode] = field(default_factory=list)
    edges: list[ProtocolEdge] = field(default_factory=list)


@dataclass
class RunRecord:
    name: str
    id: str = field(default_factory=new_id)
    sequence: int = 0
    status: str = "Prepared"
    output_dir: str = ""
    scripts: list[str] = field(default_factory=list)
    message: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    duration_seconds: float = 0.0


@dataclass
class ScymolProject:
    name: str = "Untitled project"
    project_file: str = ""
    molecules: list[MoleculeSpec] = field(
        default_factory=lambda: [
            MoleculeSpec(name="ethanol", smiles="CCO", count=2),
            MoleculeSpec(name="water", smiles="O", count=4),
        ]
    )
    system_target_density_kg_m3: float = 1000.0
    system_initial_density_fraction: float = 0.30
    system_rotate_molecules: bool = True
    random_seed: int = 1234
    system_entry_mode: str = "build"
    # ``None`` identifies projects saved before definition validation existed.
    # An empty string means that the current definition still needs validation.
    system_definition_signature: str | None = ""
    imported_structure_file: str = ""
    imported_trajectory_file: str = ""
    merge_sources: list[MergeSource] = field(default_factory=list)
    structure: StructureSettings = field(default_factory=StructureSettings)
    protocol: ProtocolGraph = field(default_factory=ProtocolGraph)
    runs: list[RunRecord] = field(default_factory=list)

    @property
    def root(self) -> Path:
        if not self.project_file:
            raise RuntimeError("Create or open a project before accessing project files.")
        return Path(self.project_file).resolve().parent

    @property
    def output_root(self) -> Path:
        return self.root / "output"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScymolProject":
        structure = StructureSettings(**data.get("structure", {}))
        protocol_data = data.get("protocol", {})
        protocol = ProtocolGraph(
            nodes=[ProtocolNode(**item) for item in protocol_data.get("nodes", [])],
            edges=[ProtocolEdge(**item) for item in protocol_data.get("edges", [])],
        )
        return cls(
            name=data.get("name", "Untitled project"),
            project_file=data.get("project_file", ""),
            molecules=[MoleculeSpec(**item) for item in data.get("molecules", [])],
            system_target_density_kg_m3=float(
                data.get("system_target_density_kg_m3", 1000.0)
            ),
            system_initial_density_fraction=float(
                data.get("system_initial_density_fraction", 0.30)
            ),
            system_rotate_molecules=bool(data.get("system_rotate_molecules", True)),
            random_seed=int(data.get("random_seed", 1234)),
            system_entry_mode=data.get("system_entry_mode", "build"),
            system_definition_signature=(
                data.get("system_definition_signature")
                if "system_definition_signature" in data
                else None
            ),
            imported_structure_file=data.get("imported_structure_file", ""),
            imported_trajectory_file=data.get("imported_trajectory_file", ""),
            merge_sources=[
                MergeSource(**item) for item in data.get("merge_sources", [])
            ],
            structure=structure,
            protocol=protocol,
            runs=[
                RunRecord(
                    **{
                        **{key: value for key, value in item.items() if key != "variables"},
                        "status": (
                            "Prepared"
                            if item.get("status", "Prepared") == "Generated"
                            else item.get("status", "Prepared")
                        ),
                    }
                )
                for item in data.get("runs", [])
            ],
        )


def system_definition_signature(project: ScymolProject) -> str:
    """Return a stable fingerprint of the Stage 1 molecular definition."""
    payload = {
        "entry_mode": project.system_entry_mode,
        "imported_structure_file": project.imported_structure_file,
        "imported_trajectory_file": project.imported_trajectory_file,
        "merge_sources": [
            {
                "id": source.id,
                "path": source.path,
                "shift_x": float(source.shift_x),
                "shift_y": float(source.shift_y),
                "shift_z": float(source.shift_z),
            }
            for source in project.merge_sources
        ],
        "molecules": [
            {
                "id": molecule.id,
                "name": molecule.name,
                "smiles": molecule.smiles,
                "count": int(molecule.count),
                "formula": molecule.formula,
                "bond_order_status": molecule.bond_order_status,
            }
            for molecule in project.molecules
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def structure_build_signature(project: ScymolProject) -> str:
    """Fingerprint every setting that affects Stage 2 derived artifacts."""
    payload = {
        "definition": system_definition_signature(project),
        "target_density_kg_m3": project.system_target_density_kg_m3,
        "initial_density_fraction": project.system_initial_density_fraction,
        "rotate_molecules": project.system_rotate_molecules,
        "random_seed": project.random_seed,
        "structure": asdict(project.structure),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
