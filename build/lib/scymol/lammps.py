from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ProtocolNode, ScymolProject
from .protocol import (
    numbered_protocol_nodes,
    parse_loop_values,
    path_label,
    protocol_paths,
    stage_label,
    validate_loop_expression,
)
from .schemas import default_parameters


THERMO_COLUMNS = "step time press vol density temp ebond eangle edihed eimp evdwl ecoul pe ke"
DUMP_COLUMNS = "id mol type q x y z"


@dataclass
class ScriptBuilder:
    lines: list[str] = field(default_factory=list)
    substage: int = 1

    def add(self, line: str = ""):
        self.lines.append(line)

    def heading(self, title: str, description: str = "", number: int | None = None):
        number = number or self.substage
        self.add("# " + "-" * 77)
        self.add(f"# Stage {number:02d}: {title}")
        if description:
            self.add(f"# {description}")
        self.add("# " + "-" * 77)
        self.substage += 1

    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"


def yn(value: Any) -> str:
    return "yes" if bool(value) else "no"


def emit_node(
    builder: ScriptBuilder,
    node: ProtocolNode,
    stage_number: int | None = None,
    parameter_values: dict[str, Any] | None = None,
    iteration: str | None = None,
):
    kind = node.kind
    p = {
        **default_parameters(kind),
        **node.parameters,
        **(parameter_values or {}),
    }
    number = stage_number or builder.substage
    output_dir = f"stages/{stage_label(node, number)}"
    if iteration:
        output_dir += f"/i_{iteration}"
    if kind == "Initialization":
        builder.heading(
            node.name,
            "Initialize LAMMPS and read the molecular topology.",
            number,
        )
        builder.add(f"log {output_dir}/log.lammps")
        for command, key in [
            ("units", "units"), ("boundary", "boundary"), ("atom_style", "atom_style"),
            ("pair_style", "pair_style"), ("pair_modify", "pair_modify"),
            ("bond_style", "bond_style"), ("angle_style", "angle_style"),
            ("dihedral_style", "dihedral_style"), ("improper_style", "improper_style"),
            ("special_bonds", "special_bonds"),
        ]:
            if str(p.get(key, "")).strip():
                builder.add(f"{command} {p[key]}")
        if str(p.get("kspace_style", "")).strip():
            builder.add(f"kspace_style {p['kspace_style']}")
        builder.add(f"read_data {p.get('structure_data', 'structure.data')}")
        builder.add(f"thermo_style custom {THERMO_COLUMNS}")
        builder.add("thermo_modify flush yes")
        builder.add(f"write_data {output_dir}/structure.data")
        builder.add("")
        return
    if kind == "Minimization":
        builder.heading(node.name, "Energy minimization.", number)
        builder.add(f"log {output_dir}/log.lammps")
        builder.add(f"min_style {p['min_style']}")
        builder.add(f"min_modify dmax {p['dmax']}")
        builder.add(f"thermo {p['thermo_every']}")
        builder.add(
            f"dump scy_min all custom {p['dump_every']} "
            f"{output_dir}/trajectory.lammpstrj {DUMP_COLUMNS}"
        )
        builder.add(
            f"minimize {p['energy_tolerance']} {p['force_tolerance']} "
            f"{p['max_iterations']} {p['max_evaluations']}"
        )
        builder.add("undump scy_min")
        builder.add(f"write_data {output_dir}/structure.data")
        builder.add("")
        return
    if kind == "Velocities":
        builder.heading(node.name, "Create initial velocities.", number)
        builder.add(f"log {output_dir}/log.lammps")
        builder.add(
            f"velocity all create {p['temperature']} {p['random_seed']} "
            f"dist {p['distribution']} mom {yn(p['momentum'])} rot {yn(p['rotation'])}"
        )
        builder.add(f"write_data {output_dir}/structure.data")
        builder.add("")
        return

    builder.heading(node.name, f"{kind} molecular dynamics.", number)
    builder.add(f"log {output_dir}/log.lammps")
    builder.add("reset_timestep 0")
    builder.add(f"thermo {p.get('thermo_every', p.get('dump_every', 1000))}")
    builder.add(f"thermo_style custom {THERMO_COLUMNS}")
    if kind == "NVT":
        builder.add(
            f"fix scy_ensemble all nvt temp {p['temperature_start']} {p['temperature_end']} "
            f"{p['temperature_damping']} drag {p['drag']}"
        )
    elif kind == "NPT":
        builder.add(
            f"fix scy_ensemble all npt temp {p['temperature_start']} {p['temperature_end']} "
            f"{p['temperature_damping']} iso {p['pressure_start']} {p['pressure_end']} "
            f"{p['pressure_damping']} drag {p['drag']}"
        )
    elif kind == "NVE":
        builder.add("fix scy_ensemble all nve")
    elif kind == "Deformation":
        axis = str(p.get("axis", "z")).lower()
        transverse_axis = next(candidate for candidate in "xyz" if candidate != axis)
        strain = "trate" if "true" in str(p.get("strain_style", "True strain")).lower() else "erate"
        timestep = p.get("timestep", 1.0)
        steps = p.get("steps", 100000)
        wall_skin = p.get("wall_skin", 2.0)
        wall_force = p.get("wall_force_constant", 10.0)
        variable_suffix = f"{number:02d}"
        rate_variable = f"scy_strain_rate_{variable_suffix}"
        rate_constant = f"scy_strain_rate_const_{variable_suffix}"
        target_ratio = f"(l{transverse_axis}+2.0*({wall_skin}))/l{axis}"
        if strain == "trate":
            rate_expression = f"log({target_ratio})/({timestep}*{steps})"
        else:
            rate_expression = f"({target_ratio}-1.0)/({timestep}*{steps})"
        builder.add(
            f"# Stop at cubic usable box: the {axis} wall spacing finishes equal to "
            f"the {transverse_axis} box length."
        )
        builder.add(f'variable {rate_variable} equal "{rate_expression}"')
        builder.add(f"variable {rate_constant} equal ${{{rate_variable}}}")
        builder.add(
            f"fix scy_ensemble all nvt temp {p['temperature_start']} {p['temperature_end']} "
            f"{p['temperature_damping']} drag {p.get('drag', 1.0)} mtk yes"
        )
        wall_high = f"scy_{axis}_wall_high_{variable_suffix}"
        wall_low = f"scy_{axis}_wall_low_{variable_suffix}"
        builder.add(f'variable {wall_high} equal "{axis}hi-{wall_skin}"')
        builder.add(f'variable {wall_low} equal "{axis}lo+{wall_skin}"')
        builder.add(
            f"fix scy_upper_wall all indent {wall_force} plane {axis} "
            f"v_{wall_high} hi units box"
        )
        builder.add(
            f"fix scy_lower_wall all indent {wall_force} plane {axis} "
            f"v_{wall_low} lo units box"
        )
        builder.add(
            f"fix scy_deform all deform {p['deform_every']} {axis} {strain} "
            f"${{{rate_constant}}} units box remap x"
        )
        deformation_variables = {
            f"scy_time_{variable_suffix}": "step*dt",
            f"scy_volume_{variable_suffix}": "vol",
            f"scy_density_{variable_suffix}": "density",
            f"scy_lx_{variable_suffix}": "lx",
            f"scy_ly_{variable_suffix}": "ly",
            f"scy_lz_{variable_suffix}": "lz",
            f"scy_sxx_{variable_suffix}": "-pxx",
            f"scy_syy_{variable_suffix}": "-pyy",
            f"scy_szz_{variable_suffix}": "-pzz",
            f"scy_syz_{variable_suffix}": "-pyz",
            f"scy_sxz_{variable_suffix}": "-pxz",
            f"scy_sxy_{variable_suffix}": "-pxy",
        }
        for variable, expression in deformation_variables.items():
            builder.add(f"variable {variable} equal {expression}")
        averaged_values = [
            f"v_scy_time_{variable_suffix}",
            "c_thermo_temp",
            "c_thermo_press",
            f"v_scy_volume_{variable_suffix}",
            f"v_scy_density_{variable_suffix}",
            f"v_scy_lx_{variable_suffix}",
            f"v_scy_ly_{variable_suffix}",
            f"v_scy_lz_{variable_suffix}",
            f"v_scy_sxx_{variable_suffix}",
            f"v_scy_syy_{variable_suffix}",
            f"v_scy_szz_{variable_suffix}",
            f"v_scy_syz_{variable_suffix}",
            f"v_scy_sxz_{variable_suffix}",
            f"v_scy_sxy_{variable_suffix}",
        ]
        builder.add(
            f"fix scy_average all ave/time {p.get('average_every', 1)} "
            f"{p.get('average_repeats', 999)} {p.get('average_frequency', 1000)} "
            f"{' '.join(averaged_values)} file {output_dir}/deformation.out"
        )
    builder.add(
        f"dump scy_dump all custom {p['dump_every']} "
        f"{output_dir}/trajectory.lammpstrj {DUMP_COLUMNS}"
    )
    builder.add(f"timestep {p['timestep']}")
    builder.add(f"run {p['steps']}")
    builder.add("unfix scy_ensemble")
    if kind == "Deformation":
        builder.add("unfix scy_average")
        builder.add("unfix scy_upper_wall")
        builder.add("unfix scy_lower_wall")
        builder.add("unfix scy_deform")
    builder.add("undump scy_dump")
    builder.add(f"write_data {output_dir}/structure.data")
    if kind == "Deformation":
        for variable in (
            rate_constant,
            rate_variable,
            wall_high,
            wall_low,
            *deformation_variables.keys(),
        ):
            builder.add(f"variable {variable} delete")
    builder.add("")


def generate_protocol_script(
    nodes: list[ProtocolNode],
    title: str = "Scymol protocol",
    stage_numbers: dict[str, int] | None = None,
) -> str:
    builder = ScriptBuilder()
    builder.add("# " + "=" * 77)
    builder.add(f"# {title}")
    builder.add("# Generated by Scymol")
    builder.add("# " + "=" * 77)
    builder.add("")
    for fallback, node in enumerate(nodes, start=1):
        number = (stage_numbers or {}).get(node.id, fallback)
        if node.loop_enabled:
            _emit_looped_node(builder, node, number)
        else:
            emit_node(builder, node, number)
    return builder.text()


def _emit_looped_node(builder: ScriptBuilder, node: ProtocolNode, number: int):
    values = parse_loop_values(node.loop_values)
    label = f"scy_loop_{number:02d}_{node.id.replace('-', '')[:8]}"
    builder.add("# " + "=" * 77)
    builder.add(f"# Loop stage {number:02d} over i = {' '.join(values)}")
    builder.add("# Use ${i} for text substitution and v_i inside equal expressions.")
    builder.add("# " + "=" * 77)
    builder.add(f"variable i index {' '.join(values)}")
    replacements: dict[str, str] = {}
    expression_variables: list[str] = []
    for field_name, expression in node.loop_expressions.items():
        expression = validate_loop_expression(expression)
        variable = f"scy_expr_{number:02d}_{field_name}"
        builder.add(f'variable {variable} equal "{expression}"')
        replacements[field_name] = f"${{{variable}}}"
        expression_variables.append(variable)
    builder.add(f"label {label}")
    emit_node(
        builder,
        node,
        number,
        parameter_values=replacements,
        iteration="${i}",
    )
    builder.add("next i")
    builder.add(f"jump SELF {label}")
    builder.add("# LAMMPS deletes the exhausted index variable i automatically.")
    for variable in expression_variables:
        builder.add(f"variable {variable} delete")
    builder.add("")


def generate_protocol_files(project: ScymolProject, output_dir: str | Path) -> list[Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = protocol_paths(project.protocol)
    numbered = numbered_protocol_nodes(project.protocol)
    stage_numbers = {node.id: number for number, node in numbered}
    for number, node in numbered:
        stage_directory = destination / "stages" / stage_label(node, number)
        stage_directory.mkdir(parents=True, exist_ok=True)
        if node.loop_enabled:
            for value in parse_loop_values(node.loop_values):
                (stage_directory / f"i_{value}").mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, nodes in enumerate(paths, start=1):
        label = path_label(nodes, index)
        target = destination / f"{label}.in"
        target.write_text(
            generate_protocol_script(nodes, title=label, stage_numbers=stage_numbers),
            encoding="utf-8",
        )
        written.append(target)
    return written
