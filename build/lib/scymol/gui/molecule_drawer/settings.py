"""Simple JSON-backed application settings."""

import json
from pathlib import Path

DEFAULT_SETTINGS = {
    "resolution_w": 1200,
    "resolution_h": 800,
    "aa_dynamic": True,
    "status_update_delay_ms": 250,
    "show_tutorial_on_startup": True,
}


def load_settings():
    path = Path(__file__).with_name("settings.json")
    settings = dict(DEFAULT_SETTINGS)

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return settings

    if isinstance(loaded, dict):
        settings.update(loaded)

    return settings


SETTINGS = load_settings()
