from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(slots=True)
class NumericDataset:
    path: Path
    columns: tuple[str, ...]
    values: np.ndarray

    def column(self, name: str) -> np.ndarray:
        return self.values[:, self.columns.index(name)]


def parse_numeric_file(path: str | Path) -> NumericDataset:
    """Parse a LAMMPS thermo log or a comment-headed numeric table."""
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Numeric result does not exist: {source}")
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    if source.name.lower() == "log.lammps" or source.suffix.lower() == ".log":
        thermo = _parse_lammps_thermo(lines)
        if thermo is not None:
            columns, rows = thermo
            return _dataset(source, columns, rows)
    columns, rows = _parse_numeric_table(lines, source.suffix.lower())
    return _dataset(source, columns, rows)


def column_statistics(values: Iterable[float]) -> dict[str, float | int]:
    data = np.asarray(list(values) if not isinstance(values, np.ndarray) else values, dtype=float)
    data = data[np.isfinite(data)]
    if not len(data):
        return {"count": 0, "mean": math.nan, "std": math.nan, "min": math.nan, "max": math.nan}
    return {
        "count": int(len(data)),
        "mean": float(np.mean(data)),
        "std": float(np.std(data, ddof=1)) if len(data) > 1 else 0.0,
        "min": float(np.min(data)),
        "max": float(np.max(data)),
    }


def downsample_xy(x, y, maximum_points: int = 20_000) -> tuple[np.ndarray, np.ndarray]:
    x_values = np.asarray(x)
    y_values = np.asarray(y)
    finite = np.isfinite(x_values) & np.isfinite(y_values)
    x_values = x_values[finite]
    y_values = y_values[finite]
    if len(x_values) <= maximum_points:
        return x_values, y_values
    indices = np.linspace(0, len(x_values) - 1, maximum_points, dtype=np.int64)
    return x_values[indices], y_values[indices]


def _dataset(path: Path, columns, rows) -> NumericDataset:
    if len(columns) < 2 or not rows:
        raise ValueError(f"No plottable numeric table was found in {path.name}.")
    values = np.asarray(rows, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(columns):
        raise ValueError(f"The numeric table in {path.name} is inconsistent.")
    return NumericDataset(path, _unique_columns(columns), values)


def _parse_lammps_thermo(lines: list[str]):
    blocks: dict[tuple[str, ...], list[list[float]]] = {}
    index = 0
    while index < len(lines):
        tokens = lines[index].strip().split()
        if len(tokens) < 2 or tokens[0].lower() != "step":
            index += 1
            continue
        columns = tuple(tokens)
        rows: list[list[float]] = []
        index += 1
        while index < len(lines):
            row_tokens = lines[index].strip().split()
            row = _numeric_row(row_tokens, len(columns))
            if row is None:
                break
            rows.append(row)
            index += 1
        if rows:
            blocks.setdefault(columns, []).extend(rows)
        index += 1
    if not blocks:
        return None
    return max(blocks.items(), key=lambda item: len(item[1]))


def _parse_numeric_table(lines: list[str], suffix: str):
    tokenized: list[tuple[list[str], bool]] = []
    comma_separated = suffix == ".csv" or any(
        "," in line for line in lines[:20] if line.strip() and not line.lstrip().startswith("#")
    )
    delimiter = "," if comma_separated else "\t" if suffix == ".tsv" else None
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        comment = stripped.startswith("#")
        content = stripped[1:].strip() if comment else stripped
        if not content:
            continue
        if delimiter:
            tokens = next(csv.reader([content], delimiter=delimiter, skipinitialspace=True))
            tokens = [token.strip() for token in tokens]
        else:
            tokens = content.split()
        if tokens:
            tokenized.append((tokens, comment))

    first_numeric = -1
    width = 0
    for index, (tokens, _) in enumerate(tokenized):
        if len(tokens) >= 2 and _numeric_row(tokens, len(tokens)) is not None:
            first_numeric = index
            width = len(tokens)
            break
    if first_numeric < 0:
        raise ValueError("No rows containing two or more numeric columns were found.")

    columns = None
    for tokens, _ in reversed(tokenized[:first_numeric]):
        if len(tokens) == width and _numeric_row(tokens, width) is None:
            columns = tokens
            break
    if columns is None:
        columns = [f"Column {index + 1}" for index in range(width)]

    rows = []
    for tokens, _ in tokenized[first_numeric:]:
        row = _numeric_row(tokens, width)
        if row is not None:
            rows.append(row)
    return columns, rows


def _numeric_row(tokens: list[str], width: int) -> list[float] | None:
    if len(tokens) != width:
        return None
    try:
        return [float(token.replace("D", "E").replace("d", "e")) for token in tokens]
    except ValueError:
        return None


def _unique_columns(columns) -> tuple[str, ...]:
    result = []
    counts: dict[str, int] = {}
    for index, raw in enumerate(columns):
        name = str(raw).strip() or f"Column {index + 1}"
        counts[name] = counts.get(name, 0) + 1
        result.append(name if counts[name] == 1 else f"{name} ({counts[name]})")
    return tuple(result)

