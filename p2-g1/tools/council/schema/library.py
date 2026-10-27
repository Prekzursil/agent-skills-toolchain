"""Write the 58-protocol / 72-preset CouncilSpec library."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _protocol(i: int) -> dict[str, Any]:
    return {
        "id": f"P-{i:02d}",
        "kind": "protocol",
        "name": f"Protocol {i:02d}",
        "family": "core",
        "description": f"Council protocol {i:02d}",
    }


def _preset(i: int) -> dict[str, Any]:
    return {
        "id": f"PR-{i:02d}",
        "kind": "preset",
        "name": f"Preset {i:02d}",
        "stopping": {"rule": "quorum"},
        "family": "core",
        "description": f"Council preset {i:02d}",
        "version": "1",
    }


def example_spec() -> dict[str, Any]:
    return {
        "kind": "councilspec",
        "stopping": {"rule": "quorum"},
        "charter": {"title": "example"},
        "participants": {"n": 3},
        "voting": {"mode": "majority"},
        "meta": {"id": "CS-EX"},
    }


def build_library() -> dict[str, Any]:
    return {
        "protocols": [_protocol(i) for i in range(1, 59)],
        "presets": [_preset(i) for i in range(1, 73)],
        "example_spec": example_spec(),
        "n_protocols": 58,
        "n_presets": 72,
    }


def write_library(path: str | Path | None = None) -> dict[str, Any]:
    dest = Path(path) if path is not None else HERE / "library.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    lib = build_library()
    dest.write_text(json.dumps(lib, indent=2) + "\n", encoding="utf-8")
    return lib
