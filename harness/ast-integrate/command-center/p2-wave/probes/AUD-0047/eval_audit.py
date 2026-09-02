#!/usr/bin/env python3
"""Evaluate workflow path filters against each gate's protected-file claim."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from path_filter import (
    AUTO_EVENTS,
    event_filters,
    extract_on,
    single_file_miss,
    would_run,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GATES_PATH = HERE / "fixtures" / "gates.json"
LIVE_GATES_PATH = HERE / "fixtures" / "live_gates.json"
AUD41_INV = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)
LIVE_WF_DIR = REPO / ".github" / "workflows"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def evaluate_gate(gate: dict[str, Any]) -> dict[str, Any]:
    wf_rel = str(gate["workflow"]).replace("\\", "/")
    wf_path = REPO / wf_rel
    row: dict[str, Any] = {
        "id": gate["id"],
        "kind": gate.get("kind") or "unknown",
        "claim": gate.get("claim") or "",
        "workflow": wf_rel,
        "workflow_exists": wf_path.is_file(),
        "protected_files": list(gate.get("protected_files") or []),
        "yaml_on_was_boolean_true": False,
        "events": [],
        "misses": [],
        "has_path_filter": False,
        "status": "ok",
    }
    if not wf_path.is_file():
        row["status"] = "workflow-absent"
        return row
    raw = wf_path.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    if not isinstance(doc, dict):
        row["status"] = "unparseable"
        return row
    row["yaml_on_was_boolean_true"] = True in doc and "on" not in doc
    on_block = extract_on(doc)
    events = event_filters(on_block)
    row["events"] = events
    row["has_path_filter"] = any(e.get("has_path_filter") for e in events)
    auto = [e for e in events if e["event"] in AUTO_EVENTS]
    if not auto:
        auto = events
    for protected in row["protected_files"]:
        miss_events = [
            e["event"]
            for e in auto
            if e.get("has_path_filter") and single_file_miss(e, protected)
        ]
        filtered_auto = [e for e in auto if e.get("has_path_filter")]
        never_seen = bool(filtered_auto) and len(miss_events) == len(filtered_auto)
        if miss_events:
            row["misses"].append(
                {
                    "protected_file": protected,
                    "miss_on_events": miss_events,
                    "never_seen_on_filtered_auto_events": never_seen,
                    "reason": (
                        "a one-file commit of this protected path would not "
                        "satisfy the event path filter"
                    ),
                }
            )
    return row


def live_gate_meta() -> dict[str, dict[str, Any]]:
    if not LIVE_GATES_PATH.is_file():
        return {}
    data = json.loads(LIVE_GATES_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for gate in data.get("gates") or []:
        name = str(gate.get("workflow_file") or "").replace("\\", "/")
        if name:
            out[name] = gate
    return out


def live_workflow_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not LIVE_WF_DIR.is_dir():
        return rows
    meta = live_gate_meta()
    files = sorted(LIVE_WF_DIR.glob("*.yml")) + sorted(LIVE_WF_DIR.glob("*.yaml"))
    for path in files:
        declared = meta.get(path.name) or {}
        gate = {
            "id": f"live:{path.name}",
            "kind": "live",
            "claim": declared.get("claim") or "undeclared-on-this-tree",
            "workflow": rel(path),
            "protected_files": list(declared.get("protected_files") or []),
        }
        row = evaluate_gate(gate)
        if not gate["protected_files"]:
            row["status"] = "live-no-declared-protected-set"
        elif row["has_path_filter"]:
            row["status"] = (
                "path-filter-miss" if row["misses"] else "path-filter-covers-protected"
            )
        else:
            row["status"] = "no-path-filter"
        rows.append(row)
    return rows


def aud41_inventory() -> dict[str, Any]:
    if not AUD41_INV.is_file():
        return {"present": False, "workflows": []}
    data = json.loads(AUD41_INV.read_text(encoding="utf-8"))
    wfs = []
    for wf in data.get("workflows") or []:
        file_rel = str(wf.get("file") or "").replace("\\", "/")
        live = (REPO / file_rel).is_file() if file_rel else False
        wfs.append(
            {
                "file": file_rel,
                "name": wf.get("name"),
                "triggers": wf.get("triggers") or [],
                "live_yaml_present": live,
                "path_filters_in_inventory": False,
                "note": (
                    "AUD-0041 stored trigger names only; paths / paths-ignore "
                    "were not captured, so they cannot be evaluated from this inventory"
                ),
            }
        )
    return {
        "present": True,
        "source": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
        "workflow_count": len(wfs),
        "live_yaml_present_count": sum(1 for w in wfs if w["live_yaml_present"]),
        "workflows": wfs,
    }


def scan() -> dict[str, Any]:
    gates_doc = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    fixture_rows = [evaluate_gate(g) for g in gates_doc.get("gates") or []]
    live_rows = live_workflow_rows()
    inv = aud41_inventory()
    misses = []
    for row in fixture_rows + live_rows:
        for miss in row.get("misses") or []:
            misses.append(
                {
                    "workflow_id": row["id"],
                    "workflow": row["workflow"],
                    "kind": row["kind"],
                    **miss,
                }
            )
    control_miss = [
        m
        for m in misses
        if m["workflow_id"] == "fixture-control-miss"
        and m["protected_file"] == "protected/secret.py"
    ]
    return {
        "live_workflows_dir_exists": LIVE_WF_DIR.is_dir(),
        "live_workflow_count": len(live_rows),
        "live_with_path_filter": sum(1 for r in live_rows if r["has_path_filter"]),
        "fixture_rows": fixture_rows,
        "live_rows": live_rows,
        "aud41": inv,
        "misses": misses,
        "fixture_miss_count": sum(1 for m in misses if m["kind"] == "fixture"),
        "live_miss_count": sum(1 for m in misses if m["kind"] == "live"),
        "control_paths_ignore_miss_reported": bool(control_miss),
    }


def predict_push(row: dict[str, Any], files: list[str]) -> bool:
    events = row.get("events") or []
    chosen = None
    for ev in events:
        if ev.get("event") == "push":
            chosen = ev
            break
    if chosen is None:
        for ev in events:
            if ev.get("event") in AUTO_EVENTS:
                chosen = ev
                break
    if chosen is None:
        return True
    return would_run(chosen, files)


def matcher_agrees_with_ledger(
    fixture_rows: list[dict[str, Any]], ledger: dict[str, Any]
) -> tuple[bool, list[str]]:
    by_id = {r["id"]: r for r in fixture_rows}
    disagreements: list[str] = []
    for commit in ledger.get("commits") or []:
        files = list(commit.get("files") or [])
        cid = commit.get("id")
        for wf_id, recorded in (commit.get("runs") or {}).items():
            row = by_id.get(wf_id)
            if not row:
                disagreements.append(f"{cid}/{wf_id}: unknown workflow")
                continue
            predicted = predict_push(row, files)
            recorded_ran = bool(recorded.get("ran"))
            if predicted != recorded_ran:
                disagreements.append(
                    f"{cid}/{wf_id}: matcher={predicted} ledger={recorded_ran}"
                )
    return not disagreements, disagreements
