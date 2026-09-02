#!/usr/bin/env python3
"""Probe 2: overclaim mutants + independent catalog overlap re-derivation."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402
import emit_teardown as E  # noqa: E402
import grade as G  # noqa: E402

ART = REPO / "command-center/research/RES-0120.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0120-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.check(doc, REPO)
    print(f"intact_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0120-probe2 intact artifact rejected")
        return 1

    mutant = copy.deepcopy(doc)
    target = next(c for c in mutant["claims"] if c.get("id") == "C-ADV-DISTRIBUTION")
    target["rails"] = [r for r in target["rails"] if r.get("kind") == G.API_KIND]
    target["grade"] = G.grade_claim(target)
    print(f"single_rail_grade={target['grade']} cited={target.get('cited_as_measured_fact')}")
    if target["grade"] != G.SINGLE:
        print("FAILED:RES-0120-probe2 single-rail mutant did not grade E3")
        return 1
    mok, mwhy = C.check(mutant, REPO)
    print(f"single_rail_check_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0120-probe2 cited E3 advantage was accepted")
        return 1

    short = copy.deepcopy(doc)
    short["competitor_advantages"] = short["competitor_advantages"][:2]
    sok, swhy = C.check(short, REPO)
    print(f"short_advantages_ok={sok} {swhy}")
    if sok:
        print("FAILED:RES-0120-probe2 two-advantage mutant accepted")
        return 1

    empty = copy.deepcopy(doc)
    empty["overlap_with_planned_features"] = []
    eok, ewhy = C.check(empty, REPO)
    print(f"empty_overlap_ok={eok} {ewhy}")
    if eok:
        print("FAILED:RES-0120-probe2 empty overlap accepted")
        return 1

    recorded = {
        row["id"]: set(row["catalog_unit_ids"])
        for row in doc["overlap_with_planned_features"]
    }
    for spec in E.FEATURE_SPECS:
        live = set(E.catalog_hits(spec["needles"]))
        rec = recorded.get(spec["id"]) or set()
        print(f"overlap {spec['id']} recorded={sorted(rec)[:4]} live={sorted(live)[:4]}")
        if not live:
            print(f"FAILED:RES-0120-probe2 catalog miss for {spec['id']}")
            return 1
        if rec != live:
            print(f"FAILED:RES-0120-probe2 overlap drift {spec['id']}")
            return 1

    print("SUCCESS:RES-0120-probe2 overclaim mutants and independent overlap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
