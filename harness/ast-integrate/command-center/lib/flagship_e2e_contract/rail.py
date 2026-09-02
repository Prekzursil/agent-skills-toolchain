"""Real vs mocked flagship e2e rails."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from .contract import independent_artifact_path

_PAD = "flagship-e2e-artifact " * 8


def run_real(blueprint_id: str, dest: Path) -> Path:
    path = independent_artifact_path(dest, blueprint_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"id": blueprint_id, "ok": True, "rail": "real", "pad": _PAD}
    path.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_mocked_only(blueprint_id: str, dest: Path) -> Any:
    mock = MagicMock(name="mocked-flagship-rail")
    mock.blueprint_id = blueprint_id
    mock.dest = str(dest)
    return mock
