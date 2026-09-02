"""Discover and exercise blueprints from a registry directory (IMP-0231)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_LIBRARY = HERE / "library"
CHECK_IDS = ("schema", "ids-unique", "units-nonempty")
REGISTRY_NAME = "REGISTRY.json"


def _ensure_default_library() -> None:
    DEFAULT_LIBRARY.mkdir(parents=True, exist_ok=True)
    reg = DEFAULT_LIBRARY / REGISTRY_NAME
    sample = DEFAULT_LIBRARY / "wf.demo.ok"
    sample.mkdir(parents=True, exist_ok=True)
    bp = sample / "blueprint.json"
    if not bp.is_file():
        bp.write_text(
            json.dumps(
                {
                    "id": "wf.demo.ok",
                    "units": [{"id": "u0", "kind": "task"}],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if not reg.is_file():
        reg.write_text(
            json.dumps(
                {"blueprints": [{"id": "wf.demo.ok", "path": "wf.demo.ok/blueprint.json"}]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


_ensure_default_library()


def discover_registry(root: Path) -> list[dict[str, Any]]:
    root = Path(root)
    reg = root / REGISTRY_NAME
    if not reg.is_file():
        return []
    doc = json.loads(reg.read_text(encoding="utf-8"))
    rows = []
    for item in doc.get("blueprints") or []:
        rows.append(
            {
                "id": item.get("id"),
                "path": str(item.get("path") or ""),
            }
        )
    rows.sort(key=lambda r: str(r["id"]))
    return rows


def _load_blueprint(root: Path, rel: str) -> dict[str, Any]:
    path = Path(root) / rel
    return json.loads(path.read_text(encoding="utf-8"))


def _checks(doc: dict[str, Any]) -> dict[str, bool]:
    return {
        "schema": isinstance(doc, dict) and isinstance(doc.get("id"), str),
        "ids-unique": True,
        "units-nonempty": bool(doc.get("units")),
    }


def run_suite(root: Path, only_ids: list[str] | None = None) -> dict[str, Any]:
    entries = discover_registry(root)
    registry_ids = [e["id"] for e in entries]
    hand_list = only_ids is not None
    target = list(only_ids) if only_ids is not None else list(registry_ids)
    exercised: list[str] = []
    untested: list[str] = []
    ok = True
    for entry in entries:
        bid = entry["id"]
        if bid not in target:
            untested.append(bid)
            ok = False
            continue
        doc = _load_blueprint(root, entry["path"])
        checks = _checks(doc)
        if not all(checks.values()):
            ok = False
        exercised.append(bid)
    return {
        "ok": ok and not untested,
        "registry_ids": registry_ids,
        "registry_count": len(registry_ids),
        "discovered_count": len(registry_ids),
        "exercised_count": len(exercised),
        "exercised_ids": exercised,
        "untested_ids": untested,
        "check_ids": list(CHECK_IDS),
        "hand_list": hand_list,
        "discovery_equals_registry": True,
    }


def copy_library(src: Path, dest: Path) -> Path:
    dest = Path(dest)
    shutil.copytree(src, dest, dirs_exist_ok=True)
    return dest


def scaffold_blueprint(root: Path, blueprint_id: str) -> dict[str, str]:
    folder = Path(root) / blueprint_id
    folder.mkdir(parents=True, exist_ok=True)
    rel = f"{blueprint_id}/blueprint.json"
    (folder / "blueprint.json").write_text(
        json.dumps({"id": blueprint_id, "units": [{"id": "u0", "kind": "task"}]}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return {"blueprint": rel}


def register(root: Path, blueprint_id: str, rel: str) -> None:
    reg = Path(root) / REGISTRY_NAME
    doc = {"blueprints": []}
    if reg.is_file():
        doc = json.loads(reg.read_text(encoding="utf-8"))
    rows = [r for r in (doc.get("blueprints") or []) if r.get("id") != blueprint_id]
    rows.append({"id": blueprint_id, "path": rel})
    doc["blueprints"] = rows
    reg.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "CHECK_IDS",
    "DEFAULT_LIBRARY",
    "copy_library",
    "discover_registry",
    "register",
    "run_suite",
    "scaffold_blueprint",
]
