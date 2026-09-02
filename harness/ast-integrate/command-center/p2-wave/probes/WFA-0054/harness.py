#!/usr/bin/env python3
"""Round-trip fidelity harness: native → IR → native with field-level diffs.

Evidence A: per-adapter exact differing-field lists on the FULL claimed corpus.
Evidence B: a planted IR mutation must be caught before any clean result is
admissible. An undeclared loss (drop not in the ledger) is a harness failure.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from adapters import ADAPTERS, Adapter, all_adapters, saved_from_ir
from corpus import UPSTREAM_ARTIFACTS, corpora
from ir import IrError, validate_ir

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = {}
            return out
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten(val, path))
        return out
    if isinstance(obj, list):
        if not obj and prefix:
            out[prefix] = []
            return out
        for i, val in enumerate(obj):
            path = f"{prefix}[{i}]"
            out.update(flatten(val, path))
        return out
    if prefix:
        out[prefix] = obj
    return out


def project(native: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: copy.deepcopy(native[key]) for key in fields if key in native}


def field_diff(
    original: dict[str, Any],
    rerendered: dict[str, Any],
    adapter: Adapter,
) -> dict[str, Any]:
    orig_c = flatten(project(original, adapter.carried_fields))
    rend_c = flatten(project(rerendered, adapter.carried_fields))
    paths = sorted(set(orig_c) | set(rend_c))
    differing: list[dict[str, Any]] = []
    for path in paths:
        if orig_c.get(path) != rend_c.get(path):
            differing.append(
                {
                    "path": path,
                    "original": orig_c.get(path, "<absent>"),
                    "rerendered": rend_c.get(path, "<absent>"),
                }
            )
    declared_observed: list[str] = []
    for field in adapter.lossy_fields:
        if field not in original:
            continue
        if field not in rerendered or rerendered.get(field) != original.get(field):
            declared_observed.append(field)
    undeclared = [row["path"] for row in differing]
    return {
        "differing_carried_fields": differing,
        "declared_lossy_observed": declared_observed,
        "undeclared_losses": undeclared,
        "clean_on_declared": not undeclared,
    }


def walk_get(obj: Any, path: tuple[Any, ...]) -> Any:
    cur = obj
    for part in path:
        cur = cur[part]
    return cur


def walk_set(obj: Any, path: tuple[Any, ...], value: Any) -> None:
    cur = obj
    for part in path[:-1]:
        cur = cur[part]
    cur[path[-1]] = value


def walk_exists(obj: Any, path: tuple[Any, ...]) -> bool:
    cur = obj
    try:
        for part in path:
            cur = cur[part]
    except (KeyError, IndexError, TypeError):
        return False
    return True


def plant_value(current: Any) -> Any:
    if isinstance(current, bool):
        return not current
    if isinstance(current, int) and not isinstance(current, bool):
        return current + 1
    if current is None:
        return "PLANTED"
    return f"PLANTED:{current}"


def pick_plant_item(adapter: Adapter, items: list[dict[str, Any]]) -> dict[str, Any]:
    for item in items:
        ir = adapter.to_ir(item)
        if walk_exists(ir, adapter.plant):
            return item
    raise RuntimeError(f"{adapter.adapter_id}: no corpus item exposes plant path {adapter.plant}")


def roundtrip_item(adapter: Adapter, native: dict[str, Any]) -> dict[str, Any]:
    ir = adapter.to_ir(native)
    validate_ir(ir)
    rerendered = adapter.from_ir(ir)
    diff = field_diff(native, rerendered, adapter)
    return {
        "corpus_id": native.get("id"),
        "ir_id": ir["id"],
        "source_anchor": ir["source_anchor"],
        **diff,
    }


def evaluate_adapter(adapter: Adapter) -> dict[str, Any]:
    items = corpora()[adapter.adapter_id]
    if not items:
        raise RuntimeError(f"{adapter.adapter_id}: empty claimed corpus")
    rows = [roundtrip_item(adapter, item) for item in items]
    undeclared = [row for row in rows if row["undeclared_losses"]]
    extra: dict[str, Any] = {}
    if adapter.adapter_id == "github-actions":
        extra["matrix_expansion"] = []
        for item in items:
            ir = adapter.to_ir(item)
            extra["matrix_expansion"].append(
                {
                    "corpus_id": item["id"],
                    "matrix": item.get("matrix"),
                    "expanded_job_count": len(ir.get("expanded_jobs") or []),
                    "job_count": len(item["jobs"]),
                }
            )
    return {
        "adapter_id": adapter.adapter_id,
        "unit_id": adapter.unit_id,
        "claimed_corpus_size": len(items),
        "ran_corpus_size": len(rows),
        "full_corpus": len(rows) == len(items),
        "declared_carried_fields": list(adapter.carried_fields),
        "declared_lossy_fields": list(adapter.lossy_fields),
        "items": rows,
        "undeclared_loss_count": sum(len(row["undeclared_losses"]) for row in rows),
        "clean_on_declared": not undeclared,
        **extra,
    }


def mutation_case(adapter: Adapter) -> dict[str, Any]:
    items = corpora()[adapter.adapter_id]
    native = pick_plant_item(adapter, items)
    clean = roundtrip_item(adapter, native)
    ir = adapter.to_ir(native)
    planted = copy.deepcopy(ir)
    current = walk_get(planted, adapter.plant)
    mutated_to = plant_value(current)
    walk_set(planted, adapter.plant, mutated_to)
    rerendered = adapter.from_ir(planted)
    planted_diff = field_diff(native, rerendered, adapter)
    caught = bool(planted_diff["undeclared_losses"] or planted_diff["differing_carried_fields"])
    return {
        "adapter_id": adapter.adapter_id,
        "corpus_id": native.get("id"),
        "plant_path": list(adapter.plant),
        "original_ir_value": current,
        "planted_ir_value": mutated_to,
        "clean_admitted": clean["clean_on_declared"],
        "planted_caught": caught,
        "planted_differing": planted_diff["differing_carried_fields"],
        "both_states_ok": clean["clean_on_declared"] and caught,
    }


def silent_drop_control() -> dict[str, Any]:
    """Detector control: drop a carried field with no ledger entry; harness must refuse."""
    adapter = ADAPTERS["saved-workflow"]
    native = corpora()["saved-workflow"][0]
    ir = adapter.to_ir(native)
    rendered = saved_from_ir(ir)
    dropped_path = "phases[0].name"
    del rendered["phases"][0]["name"]
    diff = field_diff(native, rendered, adapter)
    caught = dropped_path in diff["undeclared_losses"] or any(
        row["path"] == dropped_path for row in diff["differing_carried_fields"]
    )
    return {
        "control": "silent-drop-carried-field",
        "adapter_id": adapter.adapter_id,
        "corpus_id": native["id"],
        "dropped": dropped_path,
        "in_ledger": dropped_path.split(".")[0] in adapter.lossy_fields,
        "caught": caught,
        "undeclared_losses": diff["undeclared_losses"],
    }


def missing_anchor_control() -> dict[str, Any]:
    adapter = ADAPTERS["saved-workflow"]
    native = corpora()["saved-workflow"][0]
    ir = adapter.to_ir(native)
    broken = copy.deepcopy(ir)
    del broken["stages"][0]["source_anchor"]
    raised = False
    message = ""
    try:
        validate_ir(broken)
    except IrError as exc:
        raised = True
        message = str(exc)
    return {
        "control": "ir-node-without-source_anchor-is-invalid",
        "raised": raised,
        "message": message,
    }


def upstream_presence() -> dict[str, Any]:
    rows = {}
    for uid, rel in UPSTREAM_ARTIFACTS.items():
        path = REPO / rel
        rows[uid] = {
            "path": rel,
            "present": path.is_file() and path.stat().st_size > 0,
        }
    return rows


def evaluate_all() -> dict[str, Any]:
    adapter_rows = [evaluate_adapter(adapter) for adapter in all_adapters()]
    mutation_rows = [mutation_case(adapter) for adapter in all_adapters()]
    drop = silent_drop_control()
    anchor = missing_anchor_control()
    undeclared_total = sum(row["undeclared_loss_count"] for row in adapter_rows)
    planted_all_caught = all(row["both_states_ok"] for row in mutation_rows)
    full_corpus = all(row["full_corpus"] for row in adapter_rows)
    return {
        "adapter_count": len(adapter_rows),
        "corpus_items_total": sum(row["ran_corpus_size"] for row in adapter_rows),
        "full_corpus": full_corpus,
        "adapters": adapter_rows,
        "undeclared_total": undeclared_total,
        "planted_mutation": mutation_rows,
        "planted_all_caught": planted_all_caught,
        "silent_drop_control": drop,
        "missing_anchor_control": anchor,
        "upstream_artifacts": upstream_presence(),
        "admissible": (
            undeclared_total == 0
            and planted_all_caught
            and drop["caught"]
            and anchor["raised"]
            and full_corpus
            and len(adapter_rows) == 9
        ),
    }


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str)
