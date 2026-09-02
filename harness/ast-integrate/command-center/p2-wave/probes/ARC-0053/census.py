"""Count user-facing string slots on the live A2 typed registry schema.

Two walks (recursive vs iterative) must yield the same JSON-pointer list.
$ref is resolved. A walk that skips $ref is a negative control and MUST
differ, because workflow/preset `id` is a $ref to definitions.id.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
SCHEMA_PATH = HERE.parent / "ARC-0010" / "registry.schema.json"
REGISTRY_PATH = HERE.parent / "ARC-0010" / "registry.json"
WF_FLOOR = 96
PRESET_FLOOR = 64
WF_DEF = "workflow_blueprint"
PRESET_DEF = "council_preset"


def schema_rel() -> str:
    return SCHEMA_PATH.relative_to(REPO).as_posix()


def registry_rel() -> str:
    return REGISTRY_PATH.relative_to(REPO).as_posix()


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def resolve(root: dict[str, Any], node: Any) -> Any:
    seen: set[str] = set()
    while isinstance(node, dict) and "$ref" in node:
        ref = str(node["$ref"])
        if ref in seen:
            raise ValueError(f"cyclic $ref {ref}")
        seen.add(ref)
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref}")
        cur: Any = root
        for part in ref[2:].split("/"):
            cur = cur[part]
        node = cur
    return node


def is_string_slot(node: dict[str, Any]) -> bool:
    if node.get("type") == "string":
        return True
    const = node.get("const")
    return isinstance(const, str) and node.get("type") in (None, "string")


def _walk_properties(
    root: dict[str, Any],
    node: Any,
    path: str,
    out: list[str],
    *,
    required_only: bool,
    resolve_refs: bool,
) -> None:
    if not isinstance(node, dict):
        return
    if resolve_refs:
        node = resolve(root, node)
    elif "$ref" in node:
        return
    if is_string_slot(node):
        out.append(path)
        return
    items = node.get("items")
    if items is not None:
        if isinstance(items, dict) and (resolve_refs or "$ref" not in items):
            item = resolve(root, items) if resolve_refs else items
            if is_string_slot(item):
                out.append(path + "[]")
                return
            _walk_properties(
                root,
                items,
                path + "[]",
                out,
                required_only=required_only,
                resolve_refs=resolve_refs,
            )
        return
    props = node.get("properties") or {}
    if required_only:
        keys = [k for k in (node.get("required") or []) if k in props]
    else:
        keys = list(props.keys())
    for key in keys:
        child_path = f"{path}.{key}" if path else key
        _walk_properties(
            root,
            props[key],
            child_path,
            out,
            required_only=required_only,
            resolve_refs=resolve_refs,
        )


def string_slots_recursive(
    root: dict[str, Any],
    defn_name: str,
    *,
    required_only: bool = False,
    resolve_refs: bool = True,
) -> list[str]:
    out: list[str] = []
    _walk_properties(
        root,
        root["definitions"][defn_name],
        defn_name,
        out,
        required_only=required_only,
        resolve_refs=resolve_refs,
    )
    return sorted(out)


def string_slots_iterative(
    root: dict[str, Any],
    defn_name: str,
    *,
    required_only: bool = False,
    resolve_refs: bool = True,
) -> list[str]:
    out: list[str] = []
    stack: list[tuple[Any, str]] = [(root["definitions"][defn_name], defn_name)]
    while stack:
        node, path = stack.pop()
        if not isinstance(node, dict):
            continue
        if resolve_refs:
            node = resolve(root, node)
        elif "$ref" in node:
            continue
        if is_string_slot(node):
            out.append(path)
            continue
        items = node.get("items")
        if items is not None:
            if isinstance(items, dict):
                item = resolve(root, items) if resolve_refs else items
                if not resolve_refs and "$ref" in items:
                    continue
                if is_string_slot(item):
                    out.append(path + "[]")
                else:
                    stack.append((items, path + "[]"))
            continue
        props = node.get("properties") or {}
        if required_only:
            keys = [k for k in (node.get("required") or []) if k in props]
        else:
            keys = list(props.keys())
        for key in reversed(keys):
            child = f"{path}.{key}" if path else key
            stack.append((props[key], child))
    return sorted(out)


def instance_string_values(entry: dict[str, Any]) -> list[str]:
    found: list[str] = []

    def rec(v: Any) -> None:
        if isinstance(v, str):
            found.append(v)
        elif isinstance(v, dict):
            for child in v.values():
                rec(child)
        elif isinstance(v, list):
            for child in v:
                rec(child)

    rec(entry)
    return found


def live_entries(registry: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [e for e in registry.get("entries") or [] if e.get("kind") == kind]


def libraries_on_tree() -> dict[str, bool]:
    names = (
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "command-center/phase3/A8/DESIGN.json",
        "command-center/phase3/ROSTER.json",
        "command-center/phase3/RUBRIC.json",
        "command-center/BASELINE-SNAPSHOT.json",
    )
    return {n: (REPO / n).is_file() for n in names}


def product_strings(wf_slots: int, preset_slots: int) -> int:
    return wf_slots * WF_FLOOR + preset_slots * PRESET_FLOOR


def help_topics() -> int:
    return WF_FLOOR + PRESET_FLOOR + 2


def examples() -> int:
    return WF_FLOOR + PRESET_FLOOR


def measure() -> dict[str, Any]:
    schema = load_schema()
    registry = load_registry()
    rec_wf = string_slots_recursive(schema, WF_DEF)
    rec_pr = string_slots_recursive(schema, PRESET_DEF)
    it_wf = string_slots_iterative(schema, WF_DEF)
    it_pr = string_slots_iterative(schema, PRESET_DEF)
    req_wf = string_slots_recursive(schema, WF_DEF, required_only=True)
    req_pr = string_slots_recursive(schema, PRESET_DEF, required_only=True)
    skip_wf = string_slots_recursive(schema, WF_DEF, resolve_refs=False)
    skip_pr = string_slots_recursive(schema, PRESET_DEF, resolve_refs=False)
    rec_all = sorted(rec_wf + rec_pr)
    it_all = sorted(it_wf + it_pr)
    req_all = sorted(req_wf + req_pr)
    agree = rec_all == it_all == req_all
    skip_all = sorted(skip_wf + skip_pr)
    skip_differs = skip_all != rec_all
    wf_n = len(live_entries(registry, WF_DEF))
    pr_n = len(live_entries(registry, PRESET_DEF))
    wf_inst = [instance_string_values(e) for e in live_entries(registry, WF_DEF)]
    pr_inst = [instance_string_values(e) for e in live_entries(registry, PRESET_DEF)]
    return {
        "schema_path": schema_rel(),
        "registry_path": registry_rel(),
        "workflow_string_slots": len(rec_wf),
        "preset_string_slots": len(rec_pr),
        "recursive_paths": rec_all,
        "iterative_paths": it_all,
        "required_paths": req_all,
        "skip_ref_paths": skip_all,
        "agree": agree,
        "skip_ref_differs": skip_differs,
        "user_facing_strings": product_strings(len(rec_wf), len(rec_pr)),
        "help_topics": help_topics(),
        "examples": examples(),
        "workflow_floor": WF_FLOOR,
        "preset_floor": PRESET_FLOOR,
        "live_registry_workflow_entries": wf_n,
        "live_registry_preset_entries": pr_n,
        "live_workflow_instance_string_counts": [len(x) for x in wf_inst],
        "live_preset_instance_string_counts": [len(x) for x in pr_inst],
        "libraries_on_this_tree": libraries_on_tree(),
        "workflow_paths": rec_wf,
        "preset_paths": rec_pr,
    }


string_slots_recursive = string_slots_recursive
string_slots_iterative = string_slots_iterative
REGISTRY_PATH = REGISTRY_PATH
