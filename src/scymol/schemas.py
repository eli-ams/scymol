from __future__ import annotations

from copy import deepcopy
from typing import Any


NODE_SCHEMAS: dict[str, dict[str, Any]] = {
    "Initialization": {
        "color": "#dcebd8",
        "description": "Initialize LAMMPS and read the generated structure.",
        "fields": {
            "units": ("choice", "real", ["real", "metal", "lj"]),
            "structure_data": ("text", "structure.data"),
            "atom_style": ("choice", "full", ["full", "molecular", "atomic", "charge"]),
            "boundary": ("text", "p p p"),
            "pair_style": ("text", "lj/cut 12.0"),
            "pair_modify": ("text", "mix arithmetic"),
            "kspace_style": ("text", ""),
            "bond_style": ("text", "harmonic"),
            "angle_style": ("text", "harmonic"),
            "dihedral_style": ("text", "fourier"),
            "improper_style": ("text", "cvff"),
            "special_bonds": ("text", "amber"),
        },
    },
    "Minimization": {
        "color": "#e7e3d5",
        "description": "Relax the current structure before dynamics.",
        "fields": {
            "min_style": ("choice", "cg", ["cg", "sd", "fire", "hftn", "quickmin"]),
            "energy_tolerance": ("float", 0.0),
            "force_tolerance": ("float", 0.0),
            "max_iterations": ("int", 1000),
            "max_evaluations": ("int", 10000),
            "dmax": ("float", 0.05),
            "thermo_every": ("int", 100),
            "dump_every": ("int", 1000),
        },
    },
    "Velocities": {
        "color": "#e7dced",
        "description": "Create initial atomic velocities.",
        "fields": {
            "temperature": ("float", 298.15),
            "random_seed": ("int", 1234),
            "distribution": ("choice", "gaussian", ["gaussian", "uniform"]),
            "momentum": ("bool", True),
            "rotation": ("bool", True),
        },
    },
    "NVT": {
        "color": "#f0e0cf",
        "description": "Constant particle number, volume, and temperature dynamics.",
        "fields": {
            "temperature_start": ("float", 298.15),
            "temperature_end": ("float", 298.15),
            "temperature_damping": ("float", 100.0),
            "drag": ("float", 1.0),
            "timestep": ("float", 1.0),
            "steps": ("int", 5000),
            "thermo_every": ("int", 1000),
            "dump_every": ("int", 1000),
        },
    },
    "NPT": {
        "color": "#f3d9c9",
        "description": "Constant particle number, pressure, and temperature dynamics.",
        "fields": {
            "temperature_start": ("float", 298.15),
            "temperature_end": ("float", 298.15),
            "temperature_damping": ("float", 100.0),
            "pressure_start": ("float", 1.0),
            "pressure_end": ("float", 1.0),
            "pressure_damping": ("float", 1000.0),
            "drag": ("float", 1.0),
            "timestep": ("float", 1.0),
            "steps": ("int", 5000),
            "thermo_every": ("int", 1000),
            "dump_every": ("int", 1000),
            "set_cubic": ("bool", False),
        },
    },
    "NVE": {
        "color": "#d9e5ee",
        "description": "Constant particle number, volume, and energy dynamics.",
        "fields": {
            "timestep": ("float", 1.0),
            "steps": ("int", 5000),
            "thermo_every": ("int", 1000),
            "dump_every": ("int", 1000),
        },
    },
    "Deformation": {
        "color": "#ead8db",
        "description": "Uniaxial deformation under temperature control.",
        "fields": {
            "axis": ("choice", "z", ["x", "y", "z"]),
            "stop_at": ("choice", "Cubic usable box", ["Cubic usable box"]),
            "strain_style": ("choice", "True strain", ["True strain", "Engineering strain"]),
            "deform_every": ("int", 1000),
            "temperature_start": ("float", 298.15),
            "temperature_end": ("float", 298.15),
            "temperature_damping": ("float", 100.0),
            "drag": ("float", 1.0),
            "wall_skin": ("float", 2.0),
            "wall_force_constant": ("float", 10.0),
            "timestep": ("float", 1.0),
            "steps": ("int", 100000),
            "thermo_every": ("int", 1000),
            "dump_every": ("int", 1000),
            "average_every": ("int", 1),
            "average_repeats": ("int", 999),
            "average_frequency": ("int", 1000),
        },
    },
}


def default_parameters(kind: str) -> dict[str, Any]:
    schema = NODE_SCHEMAS[kind]
    return {name: deepcopy(spec[1]) for name, spec in schema["fields"].items()}


def coerce_value(kind: str, field_name: str, value: Any) -> Any:
    field_type = NODE_SCHEMAS[kind]["fields"][field_name][0]
    if field_type == "int":
        return int(value)
    if field_type == "float":
        return float(value)
    if field_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return str(value)
