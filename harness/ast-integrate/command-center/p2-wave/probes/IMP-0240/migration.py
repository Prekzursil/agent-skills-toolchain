"""Migration rehearsal: execute against a copy, never the live tree.

Stopping rule: halt if the rehearsal would write the production path.
Planted user-data bytes (existence + sha256) must survive the rehearsal.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def plant_user_data(root: Path, rel: str, payload: bytes) -> dict[str, Any]:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"rel": rel, "sha256": _digest(target), "bytes": len(payload), "exists": True}


def apply_schema_v2(root: Path) -> None:
    src = root / "schema" / "v1.json"
    dest = root / "schema" / "v2.json"
    doc = json.loads(src.read_text(encoding="utf-8"))
    doc["version"] = 2
    doc["migrated"] = True
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    src.unlink()


def rehearse(*, production: Path, scratch: Path, planted_rel: str) -> dict[str, Any]:
    if scratch.resolve() == production.resolve():
        return {
            "ok": False,
            "halted": True,
            "reason": "rehearsal-would-write-production",
        }
    if scratch.exists():
        shutil.rmtree(scratch)
    shutil.copytree(production, scratch)
    before = _digest(scratch / planted_rel)
    apply_schema_v2(scratch)
    after_plant = scratch / planted_rel
    prod_plant = production / planted_rel
    prod_schema_still_v1 = (production / "schema" / "v1.json").is_file()
    survived = after_plant.is_file() and _digest(after_plant) == before
    production_untouched = prod_plant.is_file() and _digest(prod_plant) == before and prod_schema_still_v1
    return {
        "ok": bool(survived and production_untouched),
        "halted": False,
        "planted_survived": survived,
        "production_untouched": production_untouched,
        "planted_sha256": before,
        "method": "copy-then-migrate",
    }


def naive_in_place(production: Path, planted_rel: str) -> dict[str, Any]:
    """Negative control: migrate the live tree. Production is mutated."""
    before = _digest(production / planted_rel)
    apply_schema_v2(production)
    return {
        "ok": False,
        "halted": False,
        "method": "in-place",
        "production_untouched": not (production / "schema" / "v2.json").is_file(),
        "planted_sha256": before,
        "reason": "wrote-production",
    }
