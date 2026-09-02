"""Scoped, non-permissive settings reader for CNF-0057.

A key is honoured only when it is declared in the schema AND written at that
key's declared scope. Unknown keys are reported. A root-scoped write of a
project-scoped key is inert. Permissive mode exists only as a both-states
control that must FAIL the unknown-key case.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BEFORE_REL = "command-center/p2-wave/probes/CNF-0057/settings_schema_before.json"
AFTER_REL = "command-center/p2-wave/probes/CNF-0057/settings_schema_after.json"
FIXTURE_REL = "command-center/p2-wave/probes/CNF-0057/fixtures"
UNKNOWN_CONTROL_KEY = "__cnf0057_unknown_key_control__"
SCHEMA_REL = "command-center/schema/regression-delta.schema.json"
_SCHEMA_STORE_RELS = (
    "command-center/schema/regression-delta.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def local_validator():
    """Draft7 validator with disk $ref store. Never follows ast-integrate.invalid to the network."""
    from jsonschema import Draft7Validator, RefResolver

    store: dict[str, Any] = {}
    for rel in _SCHEMA_STORE_RELS:
        doc = load_json(REPO / rel)
        if isinstance(doc, dict) and isinstance(doc.get("$id"), str):
            store[doc["$id"]] = doc
    schema = load_json(REPO / SCHEMA_REL)
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


def _nested_get(doc: dict[str, Any], key: str):
    if not isinstance(doc, dict):
        return None
    if key in doc:
        return doc[key]
    for bag in (doc.get("extensions"), doc.get("report")):
        if isinstance(bag, dict) and key in bag:
            return bag[key]
    return None


def fixture_loads_from(doc: dict[str, Any]) -> list[dict[str, Any]]:
    val = _nested_get(doc, "fixture_loads")
    return val if isinstance(val, list) else []


def delta_from(doc: dict[str, Any]) -> dict[str, Any]:
    val = _nested_get(doc, "delta")
    return val if isinstance(val, dict) else {}


def load_schema(state: str) -> dict[str, Any]:
    rel = BEFORE_REL if state == "before" else AFTER_REL
    doc = load_json(REPO / rel)
    if not isinstance(doc, dict) or not isinstance(doc.get("keys"), dict):
        raise ValueError(f"settings schema {rel} is not an object with keys")
    return doc


def recognised_keys(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(k): dict(v) for k, v in schema["keys"].items()}


def load_fixtures() -> list[dict[str, Any]]:
    paths = sorted((REPO / FIXTURE_REL).glob("*.json"))
    out = []
    for path in paths:
        doc = load_json(path)
        if not isinstance(doc, dict) or not doc.get("id"):
            raise ValueError(f"fixture {path} missing id")
        doc["_path"] = path.relative_to(REPO).as_posix()
        out.append(doc)
    return out


def diff_schemas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    bk = recognised_keys(before)
    ak = recognised_keys(after)
    dropped = sorted(set(bk) - set(ak))
    added = sorted(set(ak) - set(bk))
    defaults_moved: list[dict[str, Any]] = []
    scopes_changed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for name in sorted(set(bk) & set(ak)):
        b, a = bk[name], ak[name]
        row: dict[str, Any] = {"key": name}
        if b.get("default") != a.get("default"):
            defaults_moved.append(
                {
                    "key": name,
                    "before": b.get("default"),
                    "after": a.get("default"),
                    "classification": "silent-default-change",
                }
            )
            row["default"] = {"before": b.get("default"), "after": a.get("default")}
        if b.get("scope") != a.get("scope") or b.get("file") != a.get("file"):
            scopes_changed.append(
                {
                    "key": name,
                    "before_scope": b.get("scope"),
                    "after_scope": a.get("scope"),
                    "before_file": b.get("file"),
                    "after_file": a.get("file"),
                }
            )
            row["scope"] = {
                "before": b.get("scope"),
                "after": a.get("scope"),
                "before_file": b.get("file"),
                "after_file": a.get("file"),
            }
        if len(row) > 1:
            changed.append(row)
    return {
        "added": added,
        "removed": dropped,
        "changed": changed,
        "keys_dropped": dropped,
        "defaults_moved": defaults_moved,
        "scopes_changed": scopes_changed,
    }


def load_fixture(
    schema: dict[str, Any],
    fixture: dict[str, Any],
    *,
    permissive: bool = False,
) -> dict[str, Any]:
    """Apply one user fixture. permissive=True silently honours unknown keys."""
    keys = recognised_keys(schema)
    honoured: list[dict[str, Any]] = []
    inert: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    defaulted: list[dict[str, Any]] = []
    applied: dict[str, Any] = {}
    seen: set[str] = set()
    files = fixture.get("files") if isinstance(fixture.get("files"), dict) else {}
    for scope, blob in files.items():
        if not isinstance(blob, dict):
            continue
        for key, value in blob.items():
            if key not in keys:
                if permissive:
                    honoured.append(
                        {
                            "key": key,
                            "scope": scope,
                            "value": copy.deepcopy(value),
                            "permissive": True,
                        }
                    )
                    applied[key] = copy.deepcopy(value)
                    seen.add(key)
                else:
                    unknown.append(
                        {
                            "key": key,
                            "written_scope": scope,
                            "classification": "unknown-key",
                        }
                    )
                continue
            spec = keys[key]
            if spec.get("scope") != scope:
                inert.append(
                    {
                        "key": key,
                        "written_scope": scope,
                        "required_scope": spec.get("scope"),
                        "required_file": spec.get("file"),
                        "classification": "wrong-scope-inert",
                    }
                )
                continue
            honoured.append(
                {
                    "key": key,
                    "scope": scope,
                    "file": spec.get("file"),
                    "value": copy.deepcopy(value),
                }
            )
            applied[key] = copy.deepcopy(value)
            seen.add(key)
    for name, spec in keys.items():
        if name not in seen:
            defaulted.append({"key": name, "default": copy.deepcopy(spec.get("default"))})
            applied[name] = copy.deepcopy(spec.get("default"))
    written = []
    for scope, blob in files.items():
        if isinstance(blob, dict):
            written.extend(blob.keys())
    # Verbatim honour means every USER-WRITTEN declared key was applied at the
    # value they wrote. Unknown keys and inert wrong-scope writes break it.
    declared_written = [w for w in written if w in keys]
    verbatim_honour = (
        bool(declared_written)
        and not inert
        and not unknown
        and all(w in seen for w in declared_written)
    )
    if not declared_written and not unknown and not inert:
        verbatim_honour = True
    return {
        "fixture_id": fixture["id"],
        "control": fixture.get("control"),
        "path": fixture.get("_path"),
        "schema_state": schema.get("state"),
        "schema_id": schema.get("schema_id"),
        "honoured_keys": [h["key"] for h in honoured if h["key"] in keys],
        "honoured": honoured,
        "inert": inert,
        "unknown": unknown,
        "defaulted": defaulted,
        "applied": applied,
        "verbatim_honour": verbatim_honour,
        "permissive": permissive,
    }


def load_all(
    schema: dict[str, Any],
    fixtures: list[dict[str, Any]] | None = None,
    *,
    permissive: bool = False,
) -> list[dict[str, Any]]:
    return [
        load_fixture(schema, fx, permissive=permissive)
        for fx in (fixtures if fixtures is not None else load_fixtures())
    ]


def catalog_documented_defaults() -> dict[str, Any]:
    catalog = load_json(REPO / "command-center" / "WORK-UNIT-CATALOG.json")
    defaults = catalog.get("defaults") if isinstance(catalog, dict) else None
    seed_path = REPO / "tools" / "command-center" / "seed.py"
    seed_present = seed_path.is_file()
    return {
        "path": "command-center/WORK-UNIT-CATALOG.json#/defaults",
        "keys": sorted(defaults.keys()) if isinstance(defaults, dict) else [],
        "values": defaults if isinstance(defaults, dict) else {},
        "reader": "tools/command-center/validate.py:_resolved",
        "seed_defaults_present": seed_present,
        "seed_path": "tools/command-center/seed.py",
    }
