from __future__ import annotations

from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
import re
from typing import Iterable

from .models import ProtocolEdge, ProtocolGraph, ProtocolNode
from .schemas import NODE_SCHEMAS, default_parameters


def default_protocol() -> ProtocolGraph:
    kinds = ["Initialization", "Minimization", "Velocities", "NVT"]
    names = ["Initialization", "Minimization", "Velocities", "NVT"]
    nodes = [
        ProtocolNode(
            kind=kind,
            name=name,
            parameters=default_parameters(kind),
            x=index * 230.0,
            y=0.0,
        )
        for index, (kind, name) in enumerate(zip(kinds, names))
    ]
    return ProtocolGraph(
        nodes=nodes,
        edges=[ProtocolEdge(nodes[index].id, nodes[index + 1].id) for index in range(len(nodes) - 1)],
    )


def tutorial_protocol() -> ProtocolGraph:
    """Return a readable, physically coherent 298.15 K tutorial protocol."""
    graph = default_protocol()
    for node in graph.nodes:
        for parameter in ("temperature", "temperature_start", "temperature_end"):
            if parameter in node.parameters:
                node.parameters[parameter] = 298.15
        if node.kind in {"NVT", "NPT"}:
            node.parameters["thermo_every"] = 500
            node.parameters["dump_every"] = 500
    return graph


def validate_graph(graph: ProtocolGraph) -> list[str]:
    errors: list[str] = []
    node_ids = {node.id for node in graph.nodes}
    if not graph.nodes:
        return ["Add at least one protocol node."]

    for node in graph.nodes:
        if node.loop_enabled:
            if node.kind == "Initialization":
                errors.append("Initialization cannot be looped.")
            try:
                parse_loop_values(node.loop_values)
            except ValueError as exc:
                errors.append(f"{node.name}: {exc}")
            numeric_fields = {
                name
                for name, specification in NODE_SCHEMAS[node.kind]["fields"].items()
                if specification[0] in {"int", "float"}
            }
            for field_name, expression in node.loop_expressions.items():
                if field_name not in numeric_fields:
                    errors.append(
                        f"{node.name}: {field_name!r} cannot use a loop expression."
                    )
                else:
                    try:
                        validate_loop_expression(expression)
                    except ValueError as exc:
                        errors.append(
                            f"{node.name}: {field_name.replace('_', ' ')} {exc}."
                        )
        if node.kind != "Deformation":
            continue
        defaults = default_parameters("Deformation")
        parameters = {**defaults, **node.parameters}
        if str(parameters["axis"]).lower() not in {"x", "y", "z"}:
            errors.append(f"{node.name}: deformation axis must be x, y, or z.")
        if float(parameters["timestep"]) <= 0 or int(parameters["steps"]) <= 0:
            errors.append(f"{node.name}: timestep and run length must be positive.")
        every = int(parameters["average_every"])
        repeats = int(parameters["average_repeats"])
        frequency = int(parameters["average_frequency"])
        if min(every, repeats, frequency) < 1:
            errors.append(f"{node.name}: deformation averaging values must be positive.")
            continue
        if frequency % every:
            errors.append(
                f"{node.name}: average frequency must be a multiple of average every."
            )
        if every * repeats > frequency:
            errors.append(
                f"{node.name}: average repeats do not fit inside average frequency."
            )

    incoming = {node.id: 0 for node in graph.nodes}
    adjacency = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            errors.append("The graph contains a connection to a missing node.")
            continue
        incoming[edge.target] += 1
        adjacency[edge.source].append(edge.target)
    for node_id, count in incoming.items():
        if count > 1:
            name = next(node.name for node in graph.nodes if node.id == node_id)
            errors.append(f"{name} has more than one incoming connection.")

    queue = deque(node_id for node_id, count in incoming.items() if count == 0)
    visited = 0
    work_degree = dict(incoming)
    while queue:
        current = queue.popleft()
        visited += 1
        for target in adjacency[current]:
            work_degree[target] -= 1
            if work_degree[target] == 0:
                queue.append(target)
    if visited != len(graph.nodes):
        errors.append("The protocol contains a cycle.")
    return errors


def parse_loop_values(value: str) -> list[str]:
    """Normalize a LAMMPS index iterable used by one looped protocol node."""
    values = [token for token in re.split(r"[\s,]+", str(value).strip()) if token]
    if not values:
        raise ValueError("provide at least one iterator value")
    if len(set(values)) != len(values):
        raise ValueError("iterator values must be unique")
    if any(not re.fullmatch(r"[A-Za-z0-9_.+\-]+", token) for token in values):
        raise ValueError(
            "iterator values may contain only letters, numbers, dots, signs, and underscores"
        )
    return values


def validate_loop_expression(value: object) -> str:
    """Validate one expression embedded in a quoted LAMMPS variable command."""
    expression = str(value).strip()
    if not expression:
        raise ValueError("loop expression is empty")
    if any(character in expression for character in ('\r', '\n', '"')):
        raise ValueError("loop expression cannot contain quotes or line breaks")
    return expression


def topological_nodes(graph: ProtocolGraph) -> list[ProtocolNode]:
    errors = validate_graph(graph)
    if errors:
        raise ValueError(" ".join(errors))
    lookup = {node.id: node for node in graph.nodes}
    incoming = {node.id: 0 for node in graph.nodes}
    adjacency = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        incoming[edge.target] += 1
        adjacency[edge.source].append(edge.target)
    for children in adjacency.values():
        children.sort(key=lambda node_id: (lookup[node_id].y, lookup[node_id].x))
    ready = sorted(
        (lookup[node_id] for node_id, count in incoming.items() if count == 0),
        key=lambda node: (node.y, node.x),
    )
    ordered: list[ProtocolNode] = []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for target in adjacency[node.id]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(lookup[target])
                ready.sort(key=lambda item: (item.y, item.x))
    return ordered


def protocol_paths(graph: ProtocolGraph) -> list[list[ProtocolNode]]:
    errors = validate_graph(graph)
    if errors:
        raise ValueError(" ".join(errors))
    lookup = {node.id: node for node in graph.nodes}
    incoming = {node.id: 0 for node in graph.nodes}
    children = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        incoming[edge.target] += 1
        children[edge.source].append(edge.target)
    roots = sorted(
        (lookup[node_id] for node_id, count in incoming.items() if count == 0),
        key=lambda node: (node.y, node.x),
    )
    paths: list[list[ProtocolNode]] = []

    def walk(node: ProtocolNode, path: list[ProtocolNode]):
        next_path = [*path, node]
        targets = sorted(
            (lookup[node_id] for node_id in children[node.id]),
            key=lambda item: (item.y, item.x),
        )
        if not targets:
            paths.append(next_path)
            return
        for target in targets:
            walk(target, next_path)

    for root in roots:
        walk(root, [])
    return paths


def safe_label(value: str) -> str:
    text = value.strip().lower().replace(" ", "_")
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in text) or "protocol"


def numbered_protocol_nodes(graph: ProtocolGraph) -> list[tuple[int, ProtocolNode]]:
    """Return protocol nodes in the execution order shown throughout the UI."""
    return list(enumerate(topological_nodes(graph), start=1))


def stage_label(node: ProtocolNode, index: int) -> str:
    return f"{index:02d}_{safe_label(node.name or node.kind)}"


def path_label(nodes: Iterable[ProtocolNode], index: int) -> str:
    nodes = list(nodes)
    tail = safe_label(nodes[-1].name) if nodes else "empty"
    return f"protocol_{index:02d}_{tail}"


def save_protocol_preset(graph: ProtocolGraph, path: str | Path) -> Path:
    """Save a portable graph without project-specific structure paths."""
    payload = asdict(graph)
    for node in payload["nodes"]:
        if node.get("kind") == "Initialization":
            node.setdefault("parameters", {})["structure_data"] = "structure.data"
    document = {
        "format": "scymol-protocol",
        "version": 1,
        "protocol": payload,
    }
    target = Path(path)
    target.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return target


def load_protocol_preset(path: str | Path) -> ProtocolGraph:
    """Load a portable protocol preset and restore current parameter defaults."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    payload = document.get("protocol", document) if isinstance(document, dict) else None
    if not isinstance(payload, dict):
        raise ValueError("This file does not contain a Scymol protocol graph.")
    raw_nodes = payload.get("nodes", [])
    raw_edges = payload.get("edges", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("The protocol nodes or connections are malformed.")
    nodes = []
    for item in raw_nodes:
        if not isinstance(item, dict) or not item.get("kind"):
            raise ValueError("The protocol contains a malformed node.")
        kind = str(item["kind"])
        parameters = default_parameters(kind)
        parameters.update(item.get("parameters", {}))
        if kind == "Initialization":
            parameters["structure_data"] = "structure.data"
        nodes.append(
            ProtocolNode(
                id=str(item.get("id") or ""),
                kind=kind,
                name=str(item.get("name") or kind),
                parameters=parameters,
                loop_enabled=bool(item.get("loop_enabled", False)),
                loop_values=str(item.get("loop_values", "1 2 3 4")),
                loop_expressions={
                    str(key): str(value)
                    for key, value in (item.get("loop_expressions") or {}).items()
                },
                x=float(item.get("x", 0.0)),
                y=float(item.get("y", 0.0)),
            )
        )
    if any(not node.id for node in nodes) or len({node.id for node in nodes}) != len(nodes):
        raise ValueError("Protocol node identifiers are missing or duplicated.")
    edges = [
        ProtocolEdge(source=str(item["source"]), target=str(item["target"]))
        for item in raw_edges
        if isinstance(item, dict) and "source" in item and "target" in item
    ]
    graph = ProtocolGraph(nodes=nodes, edges=edges)
    errors = validate_graph(graph)
    if errors:
        raise ValueError(" ".join(errors))
    return graph
