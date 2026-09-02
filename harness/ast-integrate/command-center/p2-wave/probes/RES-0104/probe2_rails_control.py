#!/usr/bin/env python3
"""Probe 2: adversarial rails + breaking-point control.

Known-good artifact passes. Mutants that (a) cite a one-rail claim as
measured fact, (b) drop breaking_point, or (c) drop source_lineage must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402

ART = REPO / "command-center/research/RES-0104.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0104-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = C.check(doc, repo=REPO)
    print(f"good_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0104-probe2 good artifact rejected")
        return 1

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    gok, gwhy = C.check(garbage, repo=REPO)
    print(f"garbage_ok={gok} {gwhy}")
    if gok:
        print("FAILED:RES-0104-probe2 garbage accepted")
        return 1

    blocked = copy.deepcopy(doc)
    blocked["state"] = "BLOCKED"
    bok, bwhy = C.check(blocked, repo=REPO)
    print(f"blocked_ok={bok} {bwhy}")
    if bok:
        print("FAILED:RES-0104-probe2 BLOCKED accepted")
        return 1

    e3 = [c for c in doc["claims"] if c.get("evidence_tier") == "E3"]
    if not e3:
        print("FAILED:RES-0104-probe2 no E3 claim")
        return 1
    if any(c.get("cited_as_measured_fact") for c in e3):
        print("FAILED:RES-0104-probe2 E3 cited as fact")
        return 1
    print(f"e3_ids={[c['id'] for c in e3]}")

    cited = [c for c in doc["claims"] if c.get("cited_as_measured_fact")]
    if len(cited) < 2:
        print("FAILED:RES-0104-probe2 too few measured facts")
        return 1
    one = copy.deepcopy(doc)
    target = None
    for c in one["claims"]:
        if c.get("cited_as_measured_fact") and len(c.get("source_lineage") or []) >= 2:
            c["source_lineage"] = c["source_lineage"][:1]
            target = c["id"]
            break
    if target is None:
        print("FAILED:RES-0104-probe2 no two-rail fact to strip")
        return 1
    sok, swhy = C.check(one, repo=REPO)
    print(f"single_rail_fact_ok={sok} {swhy} stripped={target}")
    if sok:
        print("FAILED:RES-0104-probe2 single-rail measured fact accepted")
        return 1

    e3_promote = copy.deepcopy(doc)
    promoted = False
    for c in e3_promote["claims"]:
        if c.get("evidence_tier") == "E3":
            c["cited_as_measured_fact"] = True
            promoted = True
            break
    if not promoted:
        print("FAILED:RES-0104-probe2 no E3 to promote")
        return 1
    pok, pwhy = C.check(e3_promote, repo=REPO)
    print(f"e3_promote_ok={pok} {pwhy}")
    if pok:
        print("FAILED:RES-0104-probe2 E3 promote accepted")
        return 1

    nobp = copy.deepcopy(doc)
    del nobp["breaking_point"]
    nok, nwhy = C.check(nobp, repo=REPO)
    print(f"no_break_ok={nok} {nwhy}")
    if nok:
        print("FAILED:RES-0104-probe2 missing breaking_point accepted")
        return 1

    noline = copy.deepcopy(doc)
    del noline["source_lineage"]
    lok, lwhy = C.check(noline, repo=REPO)
    print(f"no_lineage_ok={lok} {lwhy}")
    if lok:
        print("FAILED:RES-0104-probe2 missing source_lineage accepted")
        return 1

    bp = doc["breaking_point"]
    print(
        f"breaking_point pattern={bp['pattern_id']} "
        f"breaks_above={bp['breaks_above']} unit={bp['size_unit']}"
    )
    if int(bp["breaks_above"]) < 1:
        print("FAILED:RES-0104-probe2 breaks_above")
        return 1

    print(
        "SUCCESS:RES-0104-probe2 rails, E3 control, and breaking-point "
        "discriminate both states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
