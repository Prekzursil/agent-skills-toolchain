#!/usr/bin/env python3
"""Probe 2: single shared reducer, planted local copy, uncaught mutant.

Mechanically different from probe 1 (no stub-campaign re-run as the oracle):
AST import-graph, object identity, census of engine.py vs planted local
judge, schema garbage rejection, and the reviewer voting-rule mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import schema_local as SL  # noqa: E402

import engine as E  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/phase3/A9/TEST-PLAN.json"
SCHEMA = "command-center/schema/test-plan.schema.json"


def plan_body(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged = dict(doc)
    merged.update(report)
    return merged


def main() -> int:
    if not ART.is_file() or not (REPO / SCHEMA).is_file():
        print("FAILED:ARC-0064-probe2 artifact or schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = plan_body(doc)
    errs = SL.iter_errors(REPO, doc)
    if errs:
        print("FAILED:ARC-0064-probe2 schema", errs[0])
        return 1
    for garbage in (
        {},
        {"unit_id": "ARC-0064", "state": "SUCCESS"},
        {"passing_tests": True, "ok": 1},
    ):
        g_errs = SL.iter_errors(REPO, garbage)
        if g_errs:
            print(f"garbage rejected keys={list(garbage)}")
            continue
        print("FAILED:ARC-0064-probe2 schema accepts garbage")
        return 1

    ident = E.object_identity()
    graph = E.import_graph_ok()
    engine_hits = E.engine_census_clean()
    rev = R.review()
    print(f"object_identity_proven={ident.get('object_identity_proven')}")
    print(f"all_seven_sites_same_object={ident.get('all_seven_sites_same_object')}")
    print(f"engine_imports_judge={graph.get('engine_imports_judge')}")
    print(f"all_sites_ok={graph.get('all_sites_ok')}")
    print(f"engine_census_hits={len(engine_hits)}")
    print(f"planted_detected={rev['planted_local_copy']['detected']}")
    print(
        f"uncaught {rev['uncaught_mutation']['id']} "
        f"would_stay_green={rev['uncaught_mutation']['would_stay_green']}"
    )
    if not ident.get("object_identity_proven"):
        print("FAILED:ARC-0064-probe2 object identity")
        return 1
    if not graph.get("all_sites_ok") or not graph.get("engine_imports_judge"):
        print("FAILED:ARC-0064-probe2 import graph")
        return 1
    if engine_hits:
        print(f"FAILED:ARC-0064-probe2 engine.py has census hits {engine_hits}")
        return 1
    if rev.get("verdict") != "PASS":
        print("FAILED:ARC-0064-probe2 reviewer")
        return 1
    if not rev["planted_local_copy"]["detected"]:
        print("FAILED:ARC-0064-probe2 planted local judge missed")
        return 1
    mutant = rev["uncaught_mutation"]
    if mutant.get("would_stay_green") is not True:
        print("FAILED:ARC-0064-probe2 uncaught mutant did not stay green")
        return 1
    art_pred = body.get("shared_predicate") or {}
    if art_pred.get("library") != E.LIBRARY:
        print("FAILED:ARC-0064-probe2 artifact library mismatch")
        return 1
    if art_pred.get("object_identity_proven") is not True:
        print("FAILED:ARC-0064-probe2 artifact identity flag")
        return 1
    if art_pred.get("local_copy_rejected") is not True:
        print("FAILED:ARC-0064-probe2 local_copy_rejected missing")
        return 1
    art_mut = body.get("uncaught_mutation") or (doc.get("reviewer") or {}).get(
        "uncaught_mutation"
    ) or {}
    if art_mut.get("id") != mutant.get("id"):
        print("FAILED:ARC-0064-probe2 uncaught mutation id drift")
        return 1
    if art_mut.get("would_stay_green") is not True:
        print("FAILED:ARC-0064-probe2 artifact uncaught mutant not green")
        return 1
    if (body.get("inputs_on_disk") or {}).get("a9_design_present") is True:
        print("FAILED:ARC-0064-probe2 claimed live A9 DESIGN")
        return 1
    a9 = REPO / "command-center/phase3/A9/DESIGN.json"
    if a9.is_file():
        print("FAILED:ARC-0064-probe2 A9 DESIGN appeared; this unit must not rebuild it")
        return 1
    print("SUCCESS:ARC-0064-probe2 shared-reducer identity planted-copy uncaught-mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
