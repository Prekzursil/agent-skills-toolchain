#!/usr/bin/env python3
"""Probe 2: new-file default SELECTED, and predictive selectors rejected.

Independent of probe 1: reconstructs the unmapped set from the on-disk
coverage map (does not trust engine.newfile_case alone) and requires that
secret() is missed when the unmapped test is dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import product as P  # noqa: E402
import selector as S  # noqa: E402

UNIT = "TST-0337"
MAP_PATH = HERE / "fixtures" / "coverage_map.json"


def independent_unmapped(all_tests: list[str], mapped: dict) -> list[str]:
    return [t for t in all_tests if t not in mapped]


def main() -> int:
    P.dump_coverage_map(MAP_PATH)
    doc = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    mapped = doc["tests"]
    all_tests = list(doc["all_tests"])
    unmapped = independent_unmapped(all_tests, mapped)
    if P.NEWFILE_TEST not in unmapped:
        print(f"FAILED:{UNIT}-probe2 new-file test is in the coverage map")
        return 1

    sel = S.CoverageMapSelector(mapped, all_tests)
    graph = S.DependencyGraphSelector(P.mapped_tests(), P.import_graph(), all_tests)
    changes = [
        [f"{P.LEAVES[0]}.py"],
        [f"{P.INDEPENDENT}.py"],
        ["root.py"],
        [f"{P.MIDS[3]}.py"],
    ]
    selections = []
    for changed in changes:
        got = sel.select(changed)
        selections.append(
            {
                "changed": changed,
                "selected_unmapped": [t for t in unmapped if t in got],
                "graph_unmapped": [t for t in unmapped if t in graph.select(changed)],
            }
        )
        if any(t not in got for t in unmapped):
            print(f"FAILED:{UNIT}-probe2 unmapped test not SELECTED for {changed}")
            return 1
        if any(t not in graph.select(changed) for t in unmapped):
            print(f"FAILED:{UNIT}-probe2 dep-graph dropped unmapped test for {changed}")
            return 1

    nf = E.newfile_case()
    ml = E.noml_case()

    pred = S.PredictiveSelector(all_tests)
    rejected = False
    try:
        S.reject_if_non_deterministic(pred)
    except S.SelectorRejected:
        rejected = True
    S.reject_if_non_deterministic(sel)
    S.reject_if_non_deterministic(graph)

    ok = (
        nf["all_changes_select_newfile"]
        and nf["newfile_is_the_catch"]
        and nf["mapped_only_misses_secret"]
        and ml["predictive_rejected"]
        and rejected
        and ml["graph_agrees_with_map"]
    )
    payload = {
        "probe": "probe2-newfile-noml",
        "unit_id": UNIT,
        "unmapped_from_disk_map": unmapped,
        "selections": selections,
        "secret_only_caught_by_newfile": nf["newfile_is_the_catch"],
        "mapped_only_failed": nf["mapped_only_failed"],
        "full_failed": nf["full_failed"],
        "predictive_rejected": rejected and ml["predictive_rejected"],
        "reject_message": ml["reject_message"],
        "graph_agrees_with_map": ml["graph_agrees_with_map"],
        "pass": ok,
    }
    print(json.dumps(payload, sort_keys=True))
    if not nf["mapped_only_misses_secret"]:
        print(f"FAILED:{UNIT}-probe2 mapped-only suite still caught secret() (dead control)")
        return 1
    if not nf["newfile_is_the_catch"]:
        print(f"FAILED:{UNIT}-probe2 new-file test is not the catch for secret()")
        return 1
    if not rejected:
        print(f"FAILED:{UNIT}-probe2 predictive selector was not rejected")
        return 1
    if not ml["graph_agrees_with_map"]:
        print(f"FAILED:{UNIT}-probe2 coverage-map and dep-graph diverged")
        return 1
    if not ok:
        print(f"FAILED:{UNIT}-probe2 new-file / no-ML contract")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 newfile={P.NEWFILE_TEST} always-SELECTED; "
        "secret() missed without it; predictive rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
