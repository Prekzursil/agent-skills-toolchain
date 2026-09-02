"""Recorded inverse set (REL-0002-shaped stand-in)."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "inverse_set.json"


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def effect_key(action: dict) -> str:
    target = str(action["target"]).replace("\\", "/")
    if action["action"] == "edit_settings_key":
        return f"fs:modify:{target}"
    return f"fs:create:{target}"


def recorded_keys(doc: dict | None = None) -> set[str]:
    doc = doc or load()
    return {effect_key(action) for action in doc["actions"]}


def by_id(action_id: str, doc: dict | None = None) -> dict:
    doc = doc or load()
    for action in doc["actions"]:
        if action["id"] == action_id:
            return action
    raise KeyError(action_id)
