#!/usr/bin/env python3
"""Probe 1: re-run the live matrix and require the artifact to match, no empty cells."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0025-repro-specificity.json"
SCHEMA = REPO / "command-center/schema/detector-control.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0025-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    sentinel = M.catalog_sentinel()
    if sentinel not in text:
        return fail("catalog completion_sentinel absent")
    if doc.get("matrix", {}).get("empty_cells") != 0:
        return fail("empty_cells != 0")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errors:
        return fail(f"schema {errors[0].message}")
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail("schema accepted garbage")

    live = M.run_matrix()
    classified = M.classify(live)
    art_grid = (doc.get("matrix") or {}).get("grid") or {}
    for repro_id, row in live["grid"].items():
        for comp_id, code in row.items():
            recorded = art_grid.get(repro_id, {}).get(comp_id)
            print(f"cell {repro_id} x {comp_id} live={code} artifact={recorded}")
            if recorded != code:
                return fail(f"grid mismatch {repro_id} x {comp_id}")

    n_cells = len(live["cells"])
    expected = len(live["repros"]) * len(live["components"])
    if n_cells != expected:
        return fail(f"cell count {n_cells} != {expected}")
    if len(doc.get("matrix", {}).get("cells") or []) != n_cells:
        return fail("artifact cell count mismatch")

    if classified["accepted_repros"] != doc.get("accepted_repros"):
        return fail("accepted_repros drift")
    q_live = [q["repro_id"] for q in classified["quarantined"]]
    q_art = [q["repro_id"] for q in (doc.get("quarantined") or [])]
    if q_live != q_art:
        return fail("quarantined drift")
    if "repro_nonspecific" not in q_art:
        return fail("nonspecific repro not quarantined")
    if len(classified["accepted_repros"]) < 2:
        return fail("need two specific accepted repros")
    for repro_id in classified["accepted_repros"]:
        target = live["own_target"][repro_id]
        if live["grid"][repro_id][target] != live["fire_exit"]:
            return fail(f"{repro_id} not red on {target}")
        greens = [
            hid
            for hid in classified["healthy_ids"]
            if live["grid"][repro_id][hid] == 0
        ]
        if len(greens) < 3:
            return fail(f"{repro_id} greens={greens}")
        print(f"accepted {repro_id} red_on={target} green_on={greens}")

    print("empty_cells=0 cells=" + str(n_cells))
    print("SUCCESS:CNF-0025-probe1 live matrix matches artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
