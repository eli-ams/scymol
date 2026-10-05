from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Callable

from .lammps import generate_protocol_files
from .models import RunRecord, ScymolProject
from .protocol import numbered_protocol_nodes, parse_loop_values, stage_label


def generate_run(
    project: ScymolProject,
    simulations_root: str | Path,
    sequence: int,
    name: str = "",
    progress: Callable[[str], None] | None = None,
) -> RunRecord:
    """Create an immutable prepared-simulation directory from current settings."""
    if sequence < 1:
        raise ValueError("Simulation sequence numbers must start at 1.")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    requested_name = name.strip()
    slug = _safe_simulation_name(requested_name)
    display_name = requested_name if slug else ""
    folder_name = (
        f"{sequence}_{slug}_{timestamp}" if slug else f"{sequence}_{timestamp}"
    )
    base_structure = project.output_root / "structure" / "structure.data"
    if not base_structure.is_file():
        raise FileNotFoundError(
            "Stage 2 structure.data is missing. Build the structure before preparing a simulation."
        )
    directory = Path(simulations_root) / folder_name
    directory.mkdir(parents=True, exist_ok=False)
    try:
        if progress is not None:
            progress(f"Preparing simulation {sequence} in {directory}.")
            progress("Generating LAMMPS input from the current protocol snapshot.")

        scripts = generate_protocol_files(project, directory)
        structure_copy = directory / "structure.data"
        shutil.copy2(base_structure, structure_copy)
        if progress is not None:
            progress("Copied structure.data into the simulation folder.")

        stages = [
            {
                "number": number,
                "directory": f"stages/{stage_label(node, number)}",
                "node_id": node.id,
                "name": node.name,
                "kind": node.kind,
                "loop_values": (
                    parse_loop_values(node.loop_values) if node.loop_enabled else []
                ),
            }
            for number, node in numbered_protocol_nodes(project.protocol)
        ]
        manifest = {
            "simulation_id": folder_name,
            "sequence": sequence,
            "name": display_name,
            "prepared_at": datetime.now().isoformat(timespec="seconds"),
            "molecules": [asdict(item) for item in project.molecules],
            "system": {
                "entry_mode": project.system_entry_mode,
                "target_density_kg_m3": project.system_target_density_kg_m3,
                "initial_density_fraction": project.system_initial_density_fraction,
                "rotate_molecules": project.system_rotate_molecules,
                "random_seed": project.random_seed,
            },
            "structure": asdict(project.structure),
            "protocol": asdict(project.protocol),
            "stages": stages,
            "structure_file": structure_copy.name,
            "structure_sha256": _sha256(structure_copy),
            "scripts": [path.name for path in scripts],
        }
        manifest_path = directory / "run_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if progress is not None:
            progress(f"Simulation manifest written to {manifest_path}.")
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    return RunRecord(
        name=display_name or folder_name,
        sequence=sequence,
        status="Prepared",
        output_dir=str(directory),
        scripts=[str(path) for path in scripts],
        message="LAMMPS simulation input prepared from the current protocol.",
    )


def next_simulation_sequence(project: ScymolProject) -> int:
    recorded = [int(record.sequence) for record in project.runs if record.sequence > 0]
    root = project.output_root / "simulations"
    on_disk = []
    if root.is_dir():
        for path in root.iterdir():
            if not path.is_dir():
                continue
            match = re.match(r"^(\d+)_", path.name)
            if match:
                on_disk.append(int(match.group(1)))
    return max(recorded + on_disk, default=0) + 1


def _safe_simulation_name(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._-")[:80]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
