"""IMP-0230: scaffold generator emitting a blueprint-authoring/v1 compliant skeleton.

The generator must not emit something its own gate rejects: a tool that
commits the defect class it exists to prevent has happened three times on
this estate. The self-application control (probe1) is the proof.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCAFFOLD_ID = "wf.blueprint.scaffold"


def scaffold_blueprint() -> dict[str, Any]:
    """Minimal skeleton that passes tools.blueprint_contract.contract unmodified."""
    return {
        "id": "scaffold.example",
        "title": "Scaffold blueprint (wf.blueprint.scaffold)",
        "typed_workflow": {
            "stages": [
                {"id": "plan", "type": "plan"},
                {"id": "build", "type": "build"},
                {"id": "verify", "type": "verify"},
            ]
        },
        "runnable_example": {
            "name": "noop-run",
            "command": [sys.executable, "-c", "print('scaffold example run')"],
        },
        "preset": {"id": "default", "params": {"verbosity": "quiet"}},
        "stopping_rules": [
            {"condition": "any gate fails twice", "action": "halt and report FAILED"},
            {"condition": "wall clock exceeds budget", "action": "checkpoint and stop"},
        ],
        "smoke_test": {
            "id": "hermetic-smoke",
            "hermetic": True,
            "command": [sys.executable, "-c", "raise SystemExit(0)"],
            "timeout_s": 10,
        },
        "capability_vector": {
            "network": False,
            "filesystem": ["workdir"],
            "tools": ["python"],
        },
    }


def dump_blueprint(doc: dict[str, Any]) -> str:
    """Deterministic serialization: sort_keys keeps the sha256 stable across runs."""
    return json.dumps(doc, sort_keys=True, indent=1)


def emit_scaffold(dest: str | Path) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "blueprint.json"
    path.write_bytes(dump_blueprint(scaffold_blueprint()).encode("utf-8"))
    return path
