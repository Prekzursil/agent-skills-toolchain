"""v1/v2 on-disk registry state, reverse-migration, and field comparison.

The live old loader is ARC-0010 generator.validate_registry against
a2-registry/v1 (schema_version const 1). The new writer emits schema_version 2
with two semantic remaps that a load-succeeded boolean cannot see:

  * plugin/marketplace.version becomes the format epoch ("2"); identity moves
    to release_version.
  * workflow_blueprint.discovery_only is inverted (v2 true = discovery already
    ran / execution allowed).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GEN_DIR = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010"
V1_SCHEMA = GEN_DIR / "registry.schema.json"
V1_REGISTRY = GEN_DIR / "registry.json"
V2_SCHEMA = HERE / "schemas" / "v2-state.schema.json"
FIXTURES = HERE / "fixtures"

sys.path.insert(0, str(GEN_DIR))
import generator as a2gen  # noqa: E402

OLD_LOADER = (
    "command-center/p2-wave/probes/ARC-0010/generator.py:validate_registry"
    "+registry.schema.json schema_version const 1"
)

SEMANTIC_FIELDS = (
    "entries[plugin.harness].version",
    "entries[marketplace.harness].version",
    "entries[wf.catalog-class.discovery-only].discovery_only",
)


class LoadRefuse(Exception):
    """Old version will not accept this file. Message is operator-facing."""


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def intended_v1() -> dict[str, Any]:
    doc = _load_json(V1_REGISTRY)
    a2gen.validate_registry(doc)
    return doc


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        if "entries" in obj and prefix == "":
            for k, v in obj.items():
                if k == "entries":
                    continue
                out.update(flatten(v, k))
            for item in obj["entries"]:
                eid = str(item.get("id") or "?")
                out.update(flatten(item, f"entries[{eid}]"))
            return out
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            out.update(flatten(v, key))
        return out
    if isinstance(obj, list):
        if all(not isinstance(x, (dict, list)) for x in obj):
            out[prefix] = obj
            return out
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
        return out
    out[prefix] = obj
    return out


def to_v2(v1: dict[str, Any]) -> dict[str, Any]:
    doc = copy.deepcopy(v1)
    doc["schema_version"] = 2
    doc["generator_version"] = "2.0.0"
    for entry in doc["entries"]:
        kind = entry["kind"]
        if kind in {"plugin_manifest", "marketplace_entry"}:
            entry["release_version"] = entry["version"]
            entry["version"] = "2"
        elif kind == "workflow_blueprint":
            entry["discovery_only"] = not bool(entry["discovery_only"])
        elif kind == "hook":
            entry["priority"] = 10
    jsonschema.Draft7Validator(_load_json(V2_SCHEMA)).validate(doc)
    return doc


def reverse_migrate(v2: dict[str, Any]) -> dict[str, Any]:
    ver = v2.get("schema_version")
    if ver == 1:
        return copy.deepcopy(v2)
    if ver != 2:
        raise LoadRefuse(
            f"refuse: reverse-migration cannot read schema_version={ver!r}; "
            "expected 2 (or already-1). No silent guess."
        )
    jsonschema.Draft7Validator(_load_json(V2_SCHEMA)).validate(v2)
    doc = copy.deepcopy(v2)
    doc["schema_version"] = 1
    doc["generator_version"] = "1.0.0"
    for entry in doc["entries"]:
        kind = entry["kind"]
        if kind in {"plugin_manifest", "marketplace_entry"}:
            if "release_version" not in entry:
                raise LoadRefuse(
                    "refuse: v2 entry "
                    f"{entry.get('id')!r} missing release_version; "
                    "will not treat version as plugin identity"
                )
            entry["version"] = entry.pop("release_version")
        elif kind == "workflow_blueprint":
            entry["discovery_only"] = not bool(entry["discovery_only"])
        elif kind == "hook":
            entry.pop("priority", None)
    a2gen.validate_registry(doc)
    return doc


def naive_schema_bump(v2: dict[str, Any]) -> dict[str, Any]:
    """Strip unknown keys and stamp schema_version=1. Leaves semantic remaps."""
    doc = copy.deepcopy(v2)
    doc["schema_version"] = 1
    doc["generator_version"] = "1.0.0"
    for entry in doc["entries"]:
        entry.pop("release_version", None)
        entry.pop("priority", None)
    return doc


def old_load_bytes(raw: bytes, where: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LoadRefuse(
            f"refuse: {where}: not UTF-8 ({exc}). Old v1 cannot read this file."
        ) from exc
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoadRefuse(
            f"refuse: {where}: JSONDecodeError {exc.msg} at line {exc.lineno} "
            f"col {exc.colno} (unreadable to old v1)."
        ) from exc
    if not isinstance(doc, dict):
        raise LoadRefuse(
            f"refuse: {where}: parsed {type(doc).__name__}, expected object."
        )
    ver = doc.get("schema_version")
    if ver != 1:
        raise LoadRefuse(
            f"refuse: {where}: schema_version={ver!r} is not readable by v1 "
            "(expected 1). Run reverse-migration or abort the downgrade."
        )
    try:
        jsonschema.Draft7Validator(_load_json(V1_SCHEMA)).validate(doc)
        a2gen.validate_registry(doc)
    except (jsonschema.ValidationError, ValueError) as exc:
        raise LoadRefuse(
            f"refuse: {where}: old v1 loader rejected the document: {exc}"
        ) from exc
    return doc


def old_load_path(path: Path) -> dict[str, Any]:
    rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    if not path.is_file():
        raise LoadRefuse(f"refuse: {rel}: file absent")
    return old_load_bytes(path.read_bytes(), rel)


def compare_fields(intended: dict[str, Any], loaded: dict[str, Any] | None) -> list[dict[str, Any]]:
    want = flatten(intended)
    got = flatten(loaded) if loaded is not None else {}
    keys = sorted(set(want) | set(got))
    rows: list[dict[str, Any]] = []
    for key in keys:
        a = want.get(key, None)
        b = got.get(key, None) if loaded is not None else None
        present_both = loaded is not None and key in want and key in got
        equal = present_both and a == b
        meaning_changed = present_both and a != b
        rows.append(
            {
                "path": key,
                "intended": a,
                "loaded": b,
                "equal": equal,
                "meaning_changed": meaning_changed,
            }
        )
    if not rows:
        rows.append(
            {
                "path": "(empty)",
                "intended": None,
                "loaded": None,
                "equal": False,
                "meaning_changed": False,
            }
        )
    return rows


def classify_outcome(loaded: bool, rows: list[dict[str, Any]]) -> str:
    if not loaded:
        return "REFUSES"
    if any(r["meaning_changed"] for r in rows):
        return "SILENT-MISINTERPRET"
    return "LOADS"


def ensure_fixtures() -> dict[str, Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    v1 = intended_v1()
    v2 = to_v2(v1)
    migrated = reverse_migrate(v2)
    naive = naive_schema_bump(v2)
    paths = {
        "new-written": FIXTURES / "new-written.json",
        "reverse-migrated": FIXTURES / "reverse-migrated.json",
        "naive-schema-bump": FIXTURES / "naive-schema-bump.json",
        "unreadable": FIXTURES / "unreadable.json",
    }
    paths["new-written"].write_text(_dump(v2), encoding="utf-8")
    paths["reverse-migrated"].write_text(_dump(migrated), encoding="utf-8")
    paths["naive-schema-bump"].write_text(_dump(naive), encoding="utf-8")
    paths["unreadable"].write_text('{"schema_version": 2, "entries": [', encoding="utf-8")
    return paths


def evaluate_fixture(fid: str, path: Path, intended: dict[str, Any]) -> dict[str, Any]:
    rel = path.relative_to(REPO).as_posix()
    try:
        loaded_doc = old_load_path(path)
        load = {
            "loaded": True,
            "refused": False,
            "message": f"old v1 loaded {rel} without exception",
            "where": OLD_LOADER,
        }
    except LoadRefuse as exc:
        loaded_doc = None
        load = {
            "loaded": False,
            "refused": True,
            "message": str(exc),
            "where": OLD_LOADER,
        }
    rows = compare_fields(intended, loaded_doc)
    return {
        "id": fid,
        "path": rel,
        "old_version_load": load,
        "field_comparisons": rows,
        "outcome": classify_outcome(load["loaded"], rows),
        "meaning_changed_count": sum(1 for r in rows if r["meaning_changed"]),
        "equal_count": sum(1 for r in rows if r["equal"]),
        "compared_count": len(rows),
    }


def evaluate_all() -> list[dict[str, Any]]:
    intended = intended_v1()
    paths = ensure_fixtures()
    order = (
        ("new-written", paths["new-written"]),
        ("reverse-migrated", paths["reverse-migrated"]),
        ("naive-schema-bump", paths["naive-schema-bump"]),
        ("unreadable", paths["unreadable"]),
    )
    return [evaluate_fixture(fid, path, intended) for fid, path in order]
