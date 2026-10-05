from __future__ import annotations

import json
from pathlib import Path

from .models import ScymolProject


PROJECT_FILENAME = "scymol.json"


def save_project(project: ScymolProject, path: str | Path | None = None) -> Path:
    raw_target = path or project.project_file
    if not raw_target:
        raise ValueError("A project file path is required.")
    target = Path(raw_target)
    target = target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    project.project_file = str(target)
    target.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")
    return target


def load_project(path: str | Path) -> ScymolProject:
    source = Path(path).resolve()
    project = ScymolProject.from_dict(json.loads(source.read_text(encoding="utf-8")))
    project.project_file = str(source)
    return project
