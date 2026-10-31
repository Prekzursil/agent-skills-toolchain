"""Control-registry loader for TST-0014 (rebuild, shard21-w2 resume).

registry.json maps DETECTOR-ID -> {"known_present": path, "known_broken": path}.
A detector with no registry row is UNCONTROLLED: CI (gate.py) fails while any
uncontrolled detector exists above threshold 0.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry.json"


def load_registry(path: Path | None = None) -> dict[str, dict[str, str]]:
    p = Path(path) if path is not None else REGISTRY
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("controls", data) if isinstance(data, dict) else data
    out: dict[str, dict[str, str]] = {}
    if isinstance(rows, dict):
        for did, row in rows.items():
            if isinstance(row, dict):
                out[str(did)] = row
    return out


def controls_for(detector_id: str, registry: dict[str, dict[str, str]] | None = None) -> dict[str, str] | None:
    reg = registry if registry is not None else load_registry()
    return reg.get(detector_id)


def census(detectors: list, registry: dict[str, dict[str, str]] | None = None) -> dict[str, object]:
    reg = registry if registry is not None else load_registry()
    controlled = [d for d in detectors if getattr(d, "id", None) in reg]
    uncontrolled = [d for d in detectors if getattr(d, "id", None) not in reg]
    return {
        "detector_count": len(detectors),
        "controlled_count": len(controlled),
        "uncontrolled_count": len(uncontrolled),
        "uncontrolled_ids": [d.id for d in uncontrolled][:64],
        "registry_size": len(reg),
    }
