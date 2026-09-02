#!/usr/bin/env python3
"""Probe 1: both-states short-path control + 3x5 matrix shape + schema.

Mechanically different from probe 2 (which re-runs planted leaks and compares
the documented leak table). This probe re-runs the short-path band live and
checks the catalog receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    COMPLETION_SENTINEL,
    NOT_DELIVERING,
    OPERATIONS,
    OUT_REL,
    SCHEMA_REL,
    SENTINEL,
    SHELLS,
    UNIT,
)
from matrix import compact_grid, run_experiment  # noqa: E402

ART = REPO / OUT_REL
SCHEMA = REPO / SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def load_schema() -> dict:
    root = json.loads(SCHEMA.read_text(encoding="utf-8"))
    defs = root.get("$defs") or root.get("definitions") or {}
    fragment = defs.get("portability_report")
    if not isinstance(fragment, dict):
        raise ValueError("portability_report fragment missing")
    # Keep $defs so matrix_cell $ref resolves.
    return {
        "$schema": root.get("$schema"),
        "$defs": root.get("$defs") or {},
        "definitions": root.get("definitions") or {},
        **{k: v for k, v in fragment.items() if k not in {"$id"}},
    }


def main() -> int:
    exp = run_experiment()
    short = exp["short_path_control"]
    print(
        json.dumps(
            {
                "short_all_three_visible": short["all_three_visible"],
                "short_nchars": short["path_nchars"],
                "short_visible": short["visible"],
                "short_grid": compact_grid(exp["matrix"]["short"]),
                "pass": exp["pass"],
            },
            sort_keys=True,
        )
    )
    if short["path_nchars"] >= 260:
        return fail(f"short path is not short: nchars={short['path_nchars']}")
    if not short["all_three_visible"]:
        return fail(f"short path not visible from all three: {short['visible']}")
    if not short.get("all_ops_ok"):
        return fail("short-path 3x5 matrix has a failing cell")
    for shell in SHELLS:
        for op in OPERATIONS:
            hit = [
                r
                for r in exp["matrix"]["short"]
                if r["shell"] == shell and r["op"] == op
            ]
            if len(hit) != 1 or hit[0]["ok"] is not True:
                return fail(f"short cell {shell}.{op} missing or not ok")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared {st}")
    if SENTINEL not in text or COMPLETION_SENTINEL not in text:
        return fail("sentinel absent")
    if doc.get("unit_id") != UNIT:
        return fail(f"unit_id={doc.get('unit_id')}")
    if doc.get("report_kind") != "portability_report":
        return fail(f"report_kind={doc.get('report_kind')}")
    if doc.get("short_path_control", {}).get("all_three_visible") is not True:
        return fail("artifact short_path_control.all_three_visible is not true")
    if list(doc.get("shells") or []) != list(SHELLS):
        return fail(f"artifact shells={doc.get('shells')}")
    if list(doc.get("operations") or []) != list(OPERATIONS):
        return fail(f"artifact operations={doc.get('operations')}")
    art_short = doc.get("matrix", {}).get("short") or []
    if len(art_short) != 15:
        return fail(f"artifact short matrix cells={len(art_short)}")

    schema = load_schema()
    garbage = [{}, {"totally": "unrelated"}, {"x": "x" * 200}]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.Draft7Validator(schema).validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        return fail(f"schema accepted garbage rejected={rejected}/3")
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        return fail(f"schema {errs[0].message} path={list(errs[0].path)}")

    print(
        "short_visible=True schema_garbage_rejected=3/3 "
        f"nchars={short['path_nchars']} shells={list(SHELLS)}"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 short path visible from all three; "
        "3 shells x 5 ops; schema discriminates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
