"""Live evaluation of tagged workflow fences: schema + dry-run + schema-bump detector."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_DIR = REPO / "command-center" / "schema"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SCHEMA_DIR))

from dry_run_workflow import dry_run_document  # noqa: E402
from extract import extract_docs_tree, extract_path  # noqa: E402
from validate_workflow import load_schema, validate_document  # noqa: E402

EPOCH_FIELD = "tst0254_schema_epoch"
CONTROL_REL = "command-center/p2-wave/probes/TST-0254/fixtures/extractor-control.md"


def bump_schema(schema: dict[str, Any]) -> dict[str, Any]:
    bumped = copy.deepcopy(schema)
    required = list(bumped.get("required") or [])
    if EPOCH_FIELD not in required:
        required.append(EPOCH_FIELD)
    bumped["required"] = required
    props = dict(bumped.get("properties") or {})
    props[EPOCH_FIELD] = {"type": "integer", "const": 1}
    bumped["properties"] = props
    return bumped


def schema_errors(document: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    return [
        e.message
        for e in jsonschema.Draft7Validator(schema).iter_errors(document)
    ]


def evaluate_live(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    extracted = extract_docs_tree(root)
    schema = load_schema()
    bumped = bump_schema(schema)
    rows: list[dict[str, Any]] = []
    for fence in extracted["fences"]:
        loc = f"{fence.path}:{fence.line}"
        row: dict[str, Any] = {
            "location": loc,
            "path": fence.path,
            "line": fence.line,
            "info": fence.info,
            "parse_ok": fence.document is not None and fence.parse_error is None,
            "parse_error": fence.parse_error,
            "schema_ok": False,
            "violation_id": None,
            "dry_run_ok": False,
            "dry_run_executed": False,
            "stages_planned": 0,
            "spawn_count": None,
            "stale_on_bumped_schema": False,
            "bumped_errors": [],
        }
        if fence.document is None:
            rows.append(row)
            continue
        current = validate_document(fence.document)
        row["schema_ok"] = bool(current.get("ok"))
        row["violation_id"] = current.get("violation_id")
        dry = dry_run_document(fence.document)
        row["dry_run_ok"] = bool(dry.get("ok") and dry.get("executed"))
        row["dry_run_executed"] = bool(dry.get("executed"))
        row["stages_planned"] = int(dry.get("stages_planned") or 0)
        row["spawn_count"] = dry.get("spawn_count")
        row["write_count"] = dry.get("write_count")
        row["network_count"] = dry.get("network_count")
        row["plan"] = dry.get("plan") or []
        bumped_errs = schema_errors(fence.document, bumped)
        row["bumped_errors"] = bumped_errs[:4]
        row["stale_on_bumped_schema"] = len(bumped_errs) > 0
        rows.append(row)

    n = len(rows)
    schema_pass = [r for r in rows if r["schema_ok"]]
    dry_pass = [r for r in rows if r["dry_run_ok"]]
    stale = [r for r in rows if r["stale_on_bumped_schema"]]
    epoch_control = None
    if rows and rows[0].get("parse_ok"):
        # Reconstruct first live document for the both-states epoch control.
        first_fence = extracted["fences"][0]
        if first_fence.document is not None:
            stamped = copy.deepcopy(first_fence.document)
            stamped[EPOCH_FIELD] = 1
            epoch_control = {
                "current_rejects_epoch_field": len(schema_errors(stamped, schema)) > 0,
                "bumped_accepts_epoch_field": len(schema_errors(stamped, bumped)) == 0,
            }

    return {
        "extracted": n,
        "independent_open_count": extracted["independent_open_count"],
        "count_match": extracted["count_match"],
        "scanned": extracted["scanned"],
        "present_named": extracted["present_named"],
        "missing_named": extracted["missing_named"],
        "rows": rows,
        "all_schema_ok": n > 0 and n == len(schema_pass),
        "all_dry_run_ok": n > 0 and n == len(dry_pass),
        "all_stale_on_bump": n > 0 and n == len(stale),
        "schema_pass_n": len(schema_pass),
        "dry_run_pass_n": len(dry_pass),
        "stale_on_bump_n": len(stale),
        "vacuous": n == 0,
        "epoch_control": epoch_control,
        "schema_path": "command-center/schema/workflow.schema.json",
        "dry_run_module": "command-center/schema/dry_run_workflow.py",
    }


def evaluate_extractor_control(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    path = root / CONTROL_REL
    fences = extract_path(path, root)
    tagged = [f.info for f in fences]
    text = path.read_text(encoding="utf-8")
    from extract import independent_tagged_open_count

    return {
        "path": CONTROL_REL,
        "extracted": len(fences),
        "independent": independent_tagged_open_count(text),
        "infos": tagged,
        "untagged_json_ignored": all("workflow" in (i or "").lower() for i in tagged),
        "expect": 2,
        "ok": len(fences) == 2 and independent_tagged_open_count(text) == 2,
    }


def live_contract_holds(report: dict[str, Any], control: dict[str, Any]) -> bool:
    epoch = report.get("epoch_control") or {}
    return bool(
        not report.get("vacuous")
        and report.get("count_match")
        and report.get("all_schema_ok")
        and report.get("all_dry_run_ok")
        and report.get("all_stale_on_bump")
        and epoch.get("current_rejects_epoch_field")
        and epoch.get("bumped_accepts_epoch_field")
        and control.get("ok")
        and not report.get("missing_named")
    )
