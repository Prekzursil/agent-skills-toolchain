#!/usr/bin/env python3
"""Probe 1: coverage = defined-transitions covered / defined, uncovered enumerated.

The matrix is total: every (state, event) cell is defined or explicitly rejected.
Empty defined cells fail this probe. DESIGN.json is not rebuilt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_util as SU  # noqa: E402
import suite as S  # noqa: E402
from marketplace import DEFINED  # noqa: E402

ART = REPO / "command-center/phase3/A3/TEST-PLAN.json"
DESIGN = REPO / "command-center/phase3/A3/DESIGN.json"


def main() -> int:
    if DESIGN.is_file():
        print("NOTE: A3 DESIGN.json present; not rebuilt by this unit")
    results = S.run_suite()
    failed = [r["id"] for r in results if not r.get("pass")]
    if failed:
        print(f"FAILED:ARC-0022-probe1 suite red {failed}")
        for r in results:
            if not r.get("pass"):
                print(f"  {r['id']} why={r.get('why')} state={r.get('state')} err={r.get('error')}")
        return 1
    live = S.coverage_report(results)
    total_ok, missing = S.matrix_is_total()
    if not total_ok:
        print(f"FAILED:ARC-0022-probe1 matrix not total {missing}")
        return 1
    if live["matrix_empty_defined_cells"]:
        print("FAILED:ARC-0022-probe1 empty defined cells")
        print(json.dumps(live["matrix_empty_defined_cells"][:20]))
        return 1
    if live["defined_count"] != len(DEFINED):
        print("FAILED:ARC-0022-probe1 defined_count mismatch")
        return 1
    if live["covered_count"] < 8:
        print(f"FAILED:ARC-0022-probe1 covered_count={live['covered_count']}")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ARC-0022-probe1 TEST-PLAN.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0022" not in text:
        print("FAILED:ARC-0022-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0022-probe1 self-declared {doc.get('state')}")
        return 1
    if doc.get("unit_id") != "ARC-0022":
        print("FAILED:ARC-0022-probe1 unit_id")
        return 1
    body = SU.payload(doc)
    cov = body.get("coverage") or {}
    if abs(float(cov.get("ratio")) - float(live["ratio"])) > 1e-9:
        print(f"FAILED:ARC-0022-probe1 ratio artifact={cov.get('ratio')} live={live['ratio']}")
        return 1
    if cov.get("defined_count") != live["defined_count"]:
        print("FAILED:ARC-0022-probe1 defined_count artifact drift")
        return 1
    if cov.get("covered_count") != live["covered_count"]:
        print("FAILED:ARC-0022-probe1 covered_count artifact drift")
        return 1
    art_unc = [
        (u.get("state"), u.get("event")) for u in (cov.get("uncovered") or []) if isinstance(u, dict)
    ]
    live_unc = [(u["state"], u["event"]) for u in live["uncovered"]]
    if sorted(art_unc) != sorted(live_unc):
        print("FAILED:ARC-0022-probe1 uncovered list drift")
        print(" artifact", art_unc)
        print(" live", live_unc)
        return 1

    errs = SU.schema_errors(doc)
    if errs:
        print("FAILED:ARC-0022-probe1 schema")
        for e in errs[:12]:
            print(" ", e)
        return 1
    garbage = (
        {"totally": "unrelated"},
        {"blob": "x" * 2000},
        {},
        {"state": "SUCCESS", "unit_id": "ARC-0022", "sentinel": "SUCCESS:ARC-0022"},
    )
    v = SU.validator()
    for g in garbage:
        if not list(v.iter_errors(g)):
            print("FAILED:ARC-0022-probe1 schema accepted garbage")
            return 1

    named_ids = {t["id"] for t in S.NAMED}
    art_tests = {t.get("id") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    detail = body.get("tests_detail") or []
    art_tests |= {t.get("id") for t in detail if isinstance(t, dict)}
    missing_named = sorted(named_ids - art_tests)
    if missing_named:
        print(f"FAILED:ARC-0022-probe1 named tests missing {missing_named}")
        return 1

    machine = body.get("install_state_machine") or doc.get("install_state_machine") or {}
    cells = machine.get("matrix") or body.get("matrix") or doc.get("matrix") or []
    empty = [c for c in cells if isinstance(c, dict) and not c.get("kind")]
    if empty:
        print(f"FAILED:ARC-0022-probe1 empty matrix cells {len(empty)}")
        return 1
    empty_defined = [
        c
        for c in cells
        if isinstance(c, dict) and c.get("kind") == "defined" and not c.get("covered_by")
    ]
    if empty_defined:
        print(f"FAILED:ARC-0022-probe1 empty defined cells {len(empty_defined)}")
        return 1

    out = {
        "probe": "probe1-coverage",
        "unit_id": "ARC-0022",
        "ratio": live["ratio"],
        "defined_count": live["defined_count"],
        "covered_count": live["covered_count"],
        "uncovered": live["uncovered"],
        "matrix_cells": live["matrix_cell_count"],
        "design_present": DESIGN.is_file(),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True, default=str))
    print(
        f"coverage={live['ratio']:.4f} {live['covered_count']}/{live['defined_count']} "
        f"uncovered={len(live['uncovered'])} empty_defined={len(live['matrix_empty_defined_cells'])}"
    )
    print("SUCCESS:ARC-0022-probe1 coverage computed and matrix cells filled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
