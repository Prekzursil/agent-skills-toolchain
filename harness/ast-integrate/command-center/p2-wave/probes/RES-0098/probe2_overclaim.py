#!/usr/bin/env python3
"""Probe 2: overclaim / independence control for RES-0098.

Live green: same-vendor must NOT be scored SATISFIED on different-team
or different-weights; partitioned reviewers must be disjoint and must
not claim catalog two-vendor review was done; every promoting mechanism
keeps its baseline.

Both-states: mutants that (a) mark C-TEAM SATISFIED, (b) strip a
baseline, or (c) claim two-vendor review was done must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

def find_repo(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center/WORK-UNIT-CATALOG.json").is_file():
            return p
    raise RuntimeError("cannot locate worktree root")


REPO = find_repo(Path(__file__).resolve())
ART = REPO / "command-center/research/RES-0098.json"
HARD_NO = {"C-TEAM", "C-WEIGHTS"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0098-probe2 {msg}")
    return 1


def grade(doc: dict) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    conds = {str(r.get("id")): r for r in (doc.get("conditions") or []) if isinstance(r, dict)}
    for cid in HARD_NO:
        row = conds.get(cid)
        if not row:
            return False, f"missing-{cid}"
        if row.get("same_vendor_fresh_context") == "SATISFIED":
            return False, f"{cid}-same-vendor-overclaim"
        if row.get("cross_vendor_only") is not True:
            return False, f"{cid}-not-marked-cross-vendor-only"
    if conds.get("C-CONTEXT", {}).get("same_vendor_fresh_context") != "SATISFIED":
        return False, "C-CONTEXT-should-be-the-one-satisfied-condition"
    satisfied = [
        cid
        for cid, row in conds.items()
        if row.get("same_vendor_fresh_context") == "SATISFIED"
    ]
    if set(satisfied) - {"C-CONTEXT"}:
        return False, f"unexpected-SATISFIED {satisfied}"

    for mech in doc.get("mechanisms") or []:
        if not isinstance(mech, dict):
            return False, "mechanism-not-object"
        if mech.get("promotes_condition") and not mech.get("baseline"):
            return False, f"{mech.get('id')}-headline-without-baseline"
        if (not mech.get("baseline")) and str(mech.get("evidence_tier")) in {"E1", "E2"}:
            return False, f"{mech.get('id')}-E1/E2-without-baseline"

    answer = doc.get("answer") or {}
    if answer.get("catalog_two_vendor_review_done") is True:
        return False, "overclaim-two-vendor-review"
    uncomfortable = str(answer.get("uncomfortable_case") or "").lower()
    if "one signal" not in uncomfortable:
        return False, "uncomfortable-case-missing"

    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        return False, "reviewers-not-partitioned"
    halves = []
    for rev in reviewers:
        if not isinstance(rev, dict):
            return False, "reviewer-not-object"
        if rev.get("independent_of_executor") is True:
            return False, f"{rev.get('id')}-false-independence"
        half = set(rev.get("evidence_half") or [])
        if not half:
            return False, f"{rev.get('id')}-empty-half"
        halves.append(half)
    if halves[0] & halves[1]:
        return False, f"reviewer-halves-overlap {sorted(halves[0] & halves[1])}"
    return True, "ok overclaim-controls-hold"


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = grade(doc)
    print(f"live_ok={ok} {why}")
    if not ok:
        return fail(why)

    m1 = copy.deepcopy(doc)
    for row in m1["conditions"]:
        if row.get("id") == "C-TEAM":
            row["same_vendor_fresh_context"] = "SATISFIED"
    m1ok, m1why = grade(m1)
    print(f"mutant_C-TEAM_SATISFIED ok={m1ok} {m1why}")
    if m1ok:
        return fail("mutant-C-TEAM-SATISFIED-accepted")

    m2 = copy.deepcopy(doc)
    for mech in m2["mechanisms"]:
        if mech.get("id") == "M-OSC-ATTENUATION":
            mech.pop("baseline", None)
    m2ok, m2why = grade(m2)
    print(f"mutant_drop_baseline ok={m2ok} {m2why}")
    if m2ok:
        return fail("mutant-baseline-stripped-accepted")

    m3 = copy.deepcopy(doc)
    m3["answer"]["catalog_two_vendor_review_done"] = True
    m3ok, m3why = grade(m3)
    print(f"mutant_two_vendor_claim ok={m3ok} {m3why}")
    if m3ok:
        return fail("mutant-two-vendor-claim-accepted")

    print("SUCCESS:RES-0098-probe2 overclaim independence control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
