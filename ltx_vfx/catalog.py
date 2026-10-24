"""Dependency-free, shared catalog of verified LTX Creative Lab adapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "effects.json"
CATALOG: dict[str, Any] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
EFFECTS: list[dict[str, Any]] = CATALOG["effects"]
EFFECTS_BY_ID = {effect["id"]: effect for effect in EFFECTS}


def effect_names() -> list[str]:
    """Return human-readable names in the curated UI order."""
    return [effect["name"] for effect in EFFECTS]


def get_effect(id_or_name: str) -> dict[str, Any]:
    """Resolve a stable ID or display name without silently choosing a fallback."""
    if id_or_name in EFFECTS_BY_ID:
        return EFFECTS_BY_ID[id_or_name]
    for effect in EFFECTS:
        if effect["name"] == id_or_name:
            return effect
    raise ValueError(f"Unknown LTX VFX effect: {id_or_name!r}")
