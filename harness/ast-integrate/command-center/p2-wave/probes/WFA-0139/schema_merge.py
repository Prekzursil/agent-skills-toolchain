"""Keep $defs/license-lattice in the shared foundry schema bundle."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIDECAR = HERE / "license_lattice.schema.json"
SHARED_REL = "command-center/schema/foundry-artifact.schema.json"


def lattice_def() -> dict:
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


def ensure_shared(repo: Path) -> dict:
    """Insert license-lattice without replacing sibling $defs or the root $ref.

    If the def is already present, do not rewrite the shared file (other units
    hash it).
    """
    spec = lattice_def()
    path = repo / SHARED_REL
    if path.is_file() and path.stat().st_size > 0:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raw = {}
        defs = raw.get("$defs")
        if isinstance(defs, dict) and isinstance(defs.get("license-lattice"), dict):
            return spec
        if not isinstance(defs, dict):
            defs = {}
            raw["$defs"] = defs
        defs["license-lattice"] = spec
        path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        return spec
    raw = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": SHARED_REL,
        "title": "Foundry artifacts (WFA bucket)",
        "type": "object",
        "$defs": {"license-lattice": spec},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return spec
