#!/usr/bin/env python3
"""Compute the required semver bump by diffing two artifact versions.

The verdict is derived from the pair. Callers cannot pass the bump in.
"""
from __future__ import annotations

import copy
import json
from typing import Any

RANK = {"NONE": 0, "PATCH": 1, "MINOR": 2, "MAJOR": 3}

DOC_KEYS = {"title", "description", "$comment"}
PRIVILEGE_KEYS = {"permissions", "tools", "allowed_tools", "allowed_tools_ids"}
IGNORE_INSTANCE_KEYS = {"_generated", "version"}
TIGHTER_UP = ("minimum", "minLength", "minItems", "minProperties", "minContains")
TIGHTER_DOWN = ("maximum", "maxLength", "maxItems", "maxProperties", "maxContains")


def max_bump(*bumps: str) -> str:
    best = "NONE"
    for bump in bumps:
        if RANK.get(bump, -1) > RANK[best]:
            best = bump
    return best


def pointer(base: str, key: str | int) -> str:
    token = str(key).replace("~", "~0").replace("/", "~1")
    return f"{base}/{token}" if base else f"/{token}"


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _enum_of(schema: Any) -> set[str] | None:
    if not isinstance(schema, dict):
        return None
    if "enum" in schema and isinstance(schema["enum"], list):
        return {json.dumps(v, sort_keys=True) for v in schema["enum"]}
    if "const" in schema:
        return {json.dumps(schema["const"], sort_keys=True)}
    return None


def _type_set(schema: Any) -> set[str] | None:
    if not isinstance(schema, dict) or "type" not in schema:
        return None
    return {str(t) for t in _as_list(schema["type"])}


def _required_set(schema: Any) -> set[str]:
    if not isinstance(schema, dict) or not isinstance(schema.get("required"), list):
        return set()
    return {str(x) for x in schema["required"]}


def _props(schema: Any) -> dict:
    if isinstance(schema, dict) and isinstance(schema.get("properties"), dict):
        return schema["properties"]
    return {}


def _add(rows: list[dict], kind: str, bump: str, path: str, detail: str) -> None:
    rows.append({"path": path or "/", "kind": kind, "bump": bump, "detail": detail})


def classify_schema(old: Any, new: Any, path: str = "") -> list[dict]:
    rows: list[dict] = []
    if old == new:
        return rows
    if not isinstance(old, dict) or not isinstance(new, dict):
        if old != new:
            _add(rows, "const_changed", "MAJOR", path, "non-object schema value changed")
        return rows

    old_enum, new_enum = _enum_of(old), _enum_of(new)
    if old_enum is not None and new_enum is not None:
        if new_enum < old_enum:
            _add(rows, "narrowed_enum", "MAJOR", path, f"removed {sorted(old_enum - new_enum)[:8]}")
        elif old_enum < new_enum:
            _add(rows, "widened_enum", "MINOR", path, f"added {sorted(new_enum - old_enum)[:8]}")
        elif old_enum != new_enum:
            _add(rows, "narrowed_enum", "MAJOR", path, "enum replaced with a disjoint set")
    elif old_enum is not None and new_enum is None:
        _add(rows, "widened_enum", "MINOR", path, "enum constraint removed")
    elif old_enum is None and new_enum is not None:
        _add(rows, "narrowed_enum", "MAJOR", path, "unconstrained value became enum/const")

    old_t, new_t = _type_set(old), _type_set(new)
    if old_t is not None and new_t is not None:
        if new_t < old_t:
            _add(rows, "type_narrowing", "MAJOR", path, f"{sorted(old_t)} -> {sorted(new_t)}")
        elif old_t < new_t:
            _add(rows, "type_widening", "MINOR", path, f"{sorted(old_t)} -> {sorted(new_t)}")
        elif old_t != new_t:
            _add(rows, "type_narrowing", "MAJOR", path, f"type set replaced {sorted(old_t)} -> {sorted(new_t)}")

    old_req, new_req = _required_set(old), _required_set(new)
    if new_req - old_req:
        _add(rows, "tightened_required", "MAJOR", path, f"now required: {sorted(new_req - old_req)}")
    if old_req - new_req:
        _add(rows, "loosened_required", "MINOR", path, f"no longer required: {sorted(old_req - new_req)}")

    old_props, new_props = _props(old), _props(new)
    for name in sorted(set(old_props) - set(new_props)):
        _add(rows, "removed_field", "MAJOR", pointer(pointer(path, "properties"), name), f"field {name!r} removed")
    for name in sorted(set(new_props) - set(old_props)):
        kind = "tightened_required" if name in new_req else "added_optional_field"
        bump = "MAJOR" if name in new_req else "MINOR"
        _add(rows, kind, bump, pointer(pointer(path, "properties"), name), f"field {name!r} added")
    for name in sorted(set(old_props) & set(new_props)):
        rows.extend(
            classify_schema(old_props[name], new_props[name], pointer(pointer(path, "properties"), name))
        )

    for defs_key in ("$defs", "definitions"):
        old_defs = old.get(defs_key) if isinstance(old.get(defs_key), dict) else {}
        new_defs = new.get(defs_key) if isinstance(new.get(defs_key), dict) else {}
        for name in sorted(set(old_defs) - set(new_defs)):
            _add(rows, "removed_field", "MAJOR", pointer(pointer(path, defs_key), name), f"definition {name!r} removed")
        for name in sorted(set(new_defs) - set(old_defs)):
            _add(rows, "added_definition", "MINOR", pointer(pointer(path, defs_key), name), f"definition {name!r} added")
        for name in sorted(set(old_defs) & set(new_defs)):
            rows.extend(
                classify_schema(old_defs[name], new_defs[name], pointer(pointer(path, defs_key), name))
            )

    if old.get("default") != new.get("default") and ("default" in old or "default" in new):
        _add(rows, "changed_default", "MAJOR", pointer(path, "default"), "default value changed")
    if "const" in old and "const" in new and old.get("const") != new.get("const"):
        _add(rows, "const_changed", "MAJOR", pointer(path, "const"), "const changed")

    old_ap, new_ap = old.get("additionalProperties"), new.get("additionalProperties")
    if old_ap is True and new_ap is False:
        _add(rows, "additional_properties_tightened", "MAJOR", pointer(path, "additionalProperties"), "true -> false")
    elif old_ap is False and new_ap is True:
        _add(rows, "type_widening", "MINOR", pointer(path, "additionalProperties"), "false -> true")
    elif isinstance(old_ap, dict) and isinstance(new_ap, dict):
        rows.extend(classify_schema(old_ap, new_ap, pointer(path, "additionalProperties")))
    elif old_ap != new_ap and (old_ap is not None or new_ap is not None):
        _add(
            rows,
            "additional_properties_tightened",
            "MAJOR",
            pointer(path, "additionalProperties"),
            "additionalProperties changed",
        )

    if old.get("$ref") != new.get("$ref") and ("$ref" in old or "$ref" in new):
        _add(rows, "ref_changed", "MAJOR", pointer(path, "$ref"), f"{old.get('$ref')} -> {new.get('$ref')}")

    for comb in ("oneOf", "anyOf"):
        ov, nv = old.get(comb), new.get(comb)
        if isinstance(ov, list) and isinstance(nv, list):
            if len(nv) < len(ov):
                _add(rows, "one_of_narrowed", "MAJOR", pointer(path, comb), f"{len(ov)} -> {len(nv)} branches")
            elif len(nv) > len(ov):
                _add(rows, "type_widening", "MINOR", pointer(path, comb), f"{len(ov)} -> {len(nv)} branches")
            else:
                for i, (left, right) in enumerate(zip(ov, nv)):
                    rows.extend(classify_schema(left, right, pointer(pointer(path, comb), i)))

    if isinstance(old.get("allOf"), list) and isinstance(new.get("allOf"), list):
        if len(new["allOf"]) > len(old["allOf"]):
            _add(rows, "constraint_tightened", "MAJOR", pointer(path, "allOf"), "allOf gained conjuncts")
        elif len(new["allOf"]) < len(old["allOf"]):
            _add(rows, "type_widening", "MINOR", pointer(path, "allOf"), "allOf lost conjuncts")
        else:
            for i, (left, right) in enumerate(zip(old["allOf"], new["allOf"])):
                rows.extend(classify_schema(left, right, pointer(pointer(path, "allOf"), i)))

    if isinstance(old.get("items"), dict) or isinstance(new.get("items"), dict):
        o_items = old["items"] if isinstance(old.get("items"), dict) else {}
        n_items = new["items"] if isinstance(new.get("items"), dict) else {}
        if old.get("items") != new.get("items"):
            rows.extend(classify_schema(o_items, n_items, pointer(path, "items")))

    for key in TIGHTER_UP:
        if key in old and key in new and isinstance(old[key], (int, float)) and isinstance(new[key], (int, float)):
            if new[key] > old[key]:
                _add(rows, "constraint_tightened", "MAJOR", pointer(path, key), f"{old[key]} -> {new[key]}")
            elif new[key] < old[key]:
                _add(rows, "type_widening", "MINOR", pointer(path, key), f"{old[key]} -> {new[key]}")
    for key in TIGHTER_DOWN:
        if key in old and key in new and isinstance(old[key], (int, float)) and isinstance(new[key], (int, float)):
            if new[key] < old[key]:
                _add(rows, "constraint_tightened", "MAJOR", pointer(path, key), f"{old[key]} -> {new[key]}")
            elif new[key] > old[key]:
                _add(rows, "type_widening", "MINOR", pointer(path, key), f"{old[key]} -> {new[key]}")

    if old.get("pattern") != new.get("pattern") and ("pattern" in old or "pattern" in new):
        _add(rows, "constraint_tightened", "MAJOR", pointer(path, "pattern"), "pattern changed")

    if old.get("format") != new.get("format"):
        if "format" in new and "format" not in old:
            _add(rows, "constraint_tightened", "MAJOR", pointer(path, "format"), "format added")
        elif "format" in old and "format" not in new:
            _add(rows, "format_removed", "PATCH", pointer(path, "format"), "format removed")
        elif "format" in old and "format" in new:
            _add(rows, "constraint_tightened", "MAJOR", pointer(path, "format"), "format changed")

    skip = {
        "properties",
        "required",
        "enum",
        "const",
        "type",
        "default",
        "additionalProperties",
        "$ref",
        "$defs",
        "definitions",
        "oneOf",
        "anyOf",
        "allOf",
        "items",
        "pattern",
        "format",
        *TIGHTER_UP,
        *TIGHTER_DOWN,
    }
    for key in sorted(set(old) | set(new)):
        if key in skip or old.get(key) == new.get(key):
            continue
        if key in DOC_KEYS:
            _add(rows, "description_change", "PATCH", pointer(path, key), f"{key} changed")
            continue
        ov, nv = old.get(key), new.get(key)
        if isinstance(ov, dict) and isinstance(nv, dict):
            rows.extend(classify_schema(ov, nv, pointer(path, key)))
        else:
            _add(rows, "const_changed", "MAJOR", pointer(path, key), f"keyword {key} changed")
    return rows


def _instance_keys(obj: dict) -> set[str]:
    return {k for k in obj if k not in IGNORE_INSTANCE_KEYS}


def classify_plugin(old: dict, new: dict, path: str = "") -> list[dict]:
    rows: list[dict] = []
    old_k, new_k = _instance_keys(old), _instance_keys(new)
    for name in sorted(old_k - new_k):
        _add(rows, "removed_field", "MAJOR", pointer(path, name), f"plugin field {name!r} removed")
    for name in sorted(new_k - old_k):
        if name in PRIVILEGE_KEYS:
            _add(rows, "permission_widening", "MAJOR", pointer(path, name), f"privilege field {name!r} added")
        else:
            _add(rows, "added_optional_field", "MINOR", pointer(path, name), f"plugin field {name!r} added")
    for name in sorted(old_k & new_k):
        ov, nv = old[name], new[name]
        if ov == nv:
            continue
        if name in PRIVILEGE_KEYS:
            old_set, new_set = set(_as_list(ov)), set(_as_list(nv))
            if new_set - old_set:
                _add(rows, "permission_widening", "MAJOR", pointer(path, name), "declared privilege set grew")
            elif old_set - new_set:
                _add(rows, "removed_field", "MAJOR", pointer(path, name), "declared privilege removed")
            continue
        if name in {"hooks", "hook_ids", "hook"}:
            if json.dumps(ov, sort_keys=True, default=str) != json.dumps(nv, sort_keys=True, default=str):
                _add(rows, "hook_signature_change", "MAJOR", pointer(path, name), "hook contract changed")
            continue
        if name in {"id", "name"}:
            _add(rows, "id_retirement", "MAJOR", pointer(path, name), f"{ov!r} -> {nv!r}")
            continue
        if name == "description":
            _add(rows, "description_change", "PATCH", pointer(path, name), "description changed")
            continue
        if isinstance(ov, dict) and isinstance(nv, dict):
            rows.extend(classify_plugin(ov, nv, pointer(path, name)))
        else:
            _add(rows, "const_changed", "MAJOR", pointer(path, name), f"{name} value changed")
    return rows


def classify_marketplace(old: dict, new: dict, path: str = "") -> list[dict]:
    rows: list[dict] = []
    old_k, new_k = _instance_keys(old), _instance_keys(new)
    for name in sorted(old_k - new_k):
        _add(rows, "removed_field", "MAJOR", pointer(path, name), f"marketplace field {name!r} removed")
    for name in sorted(new_k - old_k):
        _add(rows, "added_optional_field", "MINOR", pointer(path, name), f"marketplace field {name!r} added")
    for name in sorted(old_k & new_k):
        ov, nv = old[name], new[name]
        if ov == nv:
            continue
        if name in {"plugin_id", "id"}:
            _add(rows, "id_retirement", "MAJOR", pointer(path, name), f"{ov!r} -> {nv!r}")
        elif name == "description":
            _add(rows, "description_change", "PATCH", pointer(path, name), "description changed")
        else:
            _add(rows, "const_changed", "MAJOR", pointer(path, name), f"{name} changed")
    return rows


def classify_workflow(old: dict, new: dict, path: str = "") -> list[dict]:
    rows: list[dict] = []
    if old.get("id") != new.get("id") and ("id" in old or "id" in new):
        _add(rows, "id_retirement", "MAJOR", pointer(path, "id"), f"{old.get('id')!r} -> {new.get('id')!r}")
    old_k, new_k = _instance_keys(old), _instance_keys(new)
    for name in sorted(old_k - new_k):
        _add(rows, "removed_field", "MAJOR", pointer(path, name), f"workflow field {name!r} removed")
    for name in sorted(new_k - old_k):
        _add(rows, "added_optional_field", "MINOR", pointer(path, name), f"workflow field {name!r} added")

    old_stages = {s.get("id"): s for s in old.get("stages") or [] if isinstance(s, dict)}
    new_stages = {s.get("id"): s for s in new.get("stages") or [] if isinstance(s, dict)}
    for sid in sorted(x for x in set(old_stages) - set(new_stages) if x is not None):
        _add(rows, "id_retirement", "MAJOR", pointer(pointer(path, "stages"), sid), f"stage {sid!r} retired")
    for sid in sorted(x for x in set(new_stages) - set(old_stages) if x is not None):
        _add(rows, "added_optional_field", "MINOR", pointer(pointer(path, "stages"), sid), f"stage {sid!r} added")
    for sid in sorted(x for x in set(old_stages) & set(new_stages) if x is not None):
        left, right = old_stages[sid], new_stages[sid]
        if left.get("kind") != right.get("kind"):
            _add(
                rows,
                "narrowed_enum",
                "MAJOR",
                pointer(pointer(path, "stages"), sid) + "/kind",
                f"{left.get('kind')} -> {right.get('kind')}",
            )
        for fld in ("inputs", "outputs"):
            if left.get(fld) != right.get(fld):
                _add(
                    rows,
                    "const_changed",
                    "MAJOR",
                    pointer(pointer(path, "stages"), sid) + "/" + fld,
                    f"stage {fld} changed",
                )

    old_stop = old.get("stopping") if isinstance(old.get("stopping"), dict) else {}
    new_stop = new.get("stopping") if isinstance(new.get("stopping"), dict) else {}
    if old_stop.get("on_error") != new_stop.get("on_error"):
        _add(rows, "narrowed_enum", "MAJOR", pointer(pointer(path, "stopping"), "on_error"), "on_error changed")
    if old_stop.get("max_stages") != new_stop.get("max_stages") and (
        "max_stages" in old_stop or "max_stages" in new_stop
    ):
        _add(rows, "changed_default", "MAJOR", pointer(pointer(path, "stopping"), "max_stages"), "stopping default changed")
    return rows


CLASSIFIERS = {
    "schema": classify_schema,
    "plugin": classify_plugin,
    "marketplace": classify_marketplace,
    "workflow_dsl": classify_workflow,
}


def classify(old: Any, new: Any, artifact_class: str) -> dict:
    fn = CLASSIFIERS.get(artifact_class)
    if fn is None:
        raise ValueError(f"unknown artifact_class {artifact_class}")
    rows = fn(old, new)
    bump = max_bump(*(r["bump"] for r in rows)) if rows else "NONE"
    return {
        "artifact_class": artifact_class,
        "required_bump": bump,
        "changes": rows,
        "computed_not_asserted": True,
        "change_count": len(rows),
    }


def workflow_on_error_schema(registry_schema: dict) -> dict:
    wf = registry_schema["definitions"]["workflow_blueprint"]
    stop = wf["properties"]["stopping"]["properties"]["on_error"]
    if not isinstance(stop.get("enum"), list) or len(stop["enum"]) < 2:
        raise RuntimeError("workflow stopping.on_error enum missing")
    return wf


def both_states_from_registry_schema(registry_schema: dict) -> dict:
    """Catalog test: narrowed enum is MAJOR; added optional field is not."""
    workflow = copy.deepcopy(registry_schema["definitions"]["workflow_blueprint"])
    plugin = copy.deepcopy(registry_schema["definitions"]["plugin_manifest"])

    narrowed = copy.deepcopy(workflow)
    stop = narrowed["properties"]["stopping"]["properties"]["on_error"]
    original_enum = list(stop["enum"])
    stop["enum"] = [original_enum[0]]
    enum_verdict = classify(workflow, narrowed, "schema")

    additive = copy.deepcopy(plugin)
    if "homepage" in additive["properties"]:
        raise RuntimeError("homepage already present; additive control is vacuous")
    additive["properties"]["homepage"] = {"type": "string", "minLength": 1}
    add_verdict = classify(plugin, additive, "schema")

    enum_major = enum_verdict["required_bump"] == "MAJOR" and any(
        c["kind"] == "narrowed_enum" for c in enum_verdict["changes"]
    )
    add_not_major = add_verdict["required_bump"] != "MAJOR" and any(
        c["kind"] == "added_optional_field" for c in add_verdict["changes"]
    )
    return {
        "narrowed_enum_major": enum_major,
        "narrowed_enum_verdict": enum_verdict,
        "original_enum": original_enum,
        "added_optional_not_major": add_not_major,
        "added_optional_verdict": add_verdict,
        "pass": bool(enum_major and add_not_major),
    }


def _narrow_first_enum(schema: Any) -> bool:
    """Mutate the first enum with >=2 values. Prefer dropping PARTIAL when present."""
    if not isinstance(schema, dict):
        return False
    enum = schema.get("enum")
    if isinstance(enum, list) and len(enum) >= 2:
        if "PARTIAL" in enum:
            schema["enum"] = [x for x in enum if x != "PARTIAL"]
        else:
            schema["enum"] = list(enum)[:-1]
        return True
    for key in ("properties", "$defs", "definitions"):
        block = schema.get(key)
        if isinstance(block, dict):
            for child in block.values():
                if _narrow_first_enum(child):
                    return True
    items = schema.get("items")
    if isinstance(items, dict) and _narrow_first_enum(items):
        return True
    for comb in ("oneOf", "anyOf", "allOf"):
        branches = schema.get(comb)
        if isinstance(branches, list):
            for child in branches:
                if _narrow_first_enum(child):
                    return True
    return False


def calculator_control(live_schema: dict) -> dict:
    """Detect a planted breaking change before trusting an identity NONE."""
    planted = copy.deepcopy(live_schema)
    planted_kind = "removed_field"
    if _narrow_first_enum(planted):
        planted_kind = "narrowed_enum"
    else:
        props = planted.setdefault("properties", {})
        if not props:
            raise RuntimeError("control schema has no properties to break")
        victim = sorted(props)[0]
        props.pop(victim)
        planted["required"] = [r for r in planted.get("required") or [] if r != victim]

    broken = classify(live_schema, planted, "schema")
    detected = broken["required_bump"] == "MAJOR" and any(
        c["kind"] in {"narrowed_enum", "removed_field"} for c in broken["changes"]
    )
    identity = classify(live_schema, copy.deepcopy(live_schema), "schema")
    identity_none = identity["required_bump"] == "NONE" and identity["change_count"] == 0
    trusted = bool(detected and identity_none)
    return {
        "planted_kind": planted_kind,
        "detected_breaking": detected,
        "breaking_verdict": broken,
        "identity_none": identity_none,
        "identity_verdict": identity,
        "trusted_identity_after_control": trusted,
        "pass": trusted,
    }


def extra_machine_checks() -> dict:
    base = {
        "type": "object",
        "properties": {
            "a": {"type": "string", "enum": ["x", "y"], "default": "x"},
            "b": {"type": "integer"},
        },
        "required": ["a"],
        "additionalProperties": False,
    }
    removed = copy.deepcopy(base)
    removed["properties"].pop("b")
    tightened = copy.deepcopy(base)
    tightened["required"] = ["a", "b"]
    defaulted = copy.deepcopy(base)
    defaulted["properties"]["a"]["default"] = "y"
    rows = {
        "removed_field": classify(base, removed, "schema"),
        "tightened_required": classify(base, tightened, "schema"),
        "changed_default": classify(base, defaulted, "schema"),
        "permission_widening": classify(
            {"name": "p", "hooks": ["h"], "permissions": ["read"]},
            {"name": "p", "hooks": ["h"], "permissions": ["read", "write"]},
            "plugin",
        ),
    }
    ok = (
        rows["removed_field"]["required_bump"] == "MAJOR"
        and rows["tightened_required"]["required_bump"] == "MAJOR"
        and rows["changed_default"]["required_bump"] == "MAJOR"
        and rows["permission_widening"]["required_bump"] == "MAJOR"
    )
    return {"pass": ok, "rows": rows}
