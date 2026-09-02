#!/usr/bin/env python3
"""Probe 1: condition-by-condition contract on RES-0098.

Live green: the artifact names each condition, scores same-vendor
fresh-context, and names at least one cross-vendor-only condition.
Both-states: a mutant that drops the cross-vendor-only flags must fail.
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
SENTINEL = (
    "SUCCESS:RES-0098 in the receipt AND a condition-by-condition "
    "satisfiability verdict for same-vendor fresh context, with at least "
    "one cross-vendor-only condition named"
)
ALLOWED = {"SATISFIED", "PARTIAL", "NOT-SATISFIED"}
ALLOWED_STATE = {"SUCCESS", "PARTIAL"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0098-probe1 {msg}")
    return 1


def grade(doc: dict) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    if str(doc.get("state") or "").upper() not in ALLOWED_STATE:
        return False, f"state={doc.get('state')}"
    blob = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in blob:
        return False, "sentinel-absent"
    conds = doc.get("conditions") or []
    if not isinstance(conds, list) or len(conds) < 6:
        return False, f"conditions-too-few n={len(conds) if isinstance(conds, list) else 0}"
    ids = []
    cross = []
    for row in conds:
        if not isinstance(row, dict):
            return False, "condition-not-object"
        cid = str(row.get("id") or "")
        if not cid:
            return False, "condition-id-missing"
        ids.append(cid)
        v = str(row.get("same_vendor_fresh_context") or "")
        if v not in ALLOWED:
            return False, f"{cid}-bad-verdict={v}"
        if row.get("cross_vendor_only") is True:
            if v == "SATISFIED":
                return False, f"{cid}-cross-vendor-only-but-same-vendor-SATISFIED"
            cross.append(cid)
    if len(set(ids)) != len(ids):
        return False, "duplicate-condition-ids"
    if not cross:
        return False, "no-cross-vendor-only-condition"
    mechs = doc.get("mechanisms") or []
    if not isinstance(mechs, list) or len(mechs) < 4:
        return False, "mechanisms-too-few"
    promoted = 0
    for mech in mechs:
        if not isinstance(mech, dict):
            return False, "mechanism-not-object"
        if not mech.get("section_or_figure"):
            return False, f"{mech.get('id')}-missing-section"
        if not mech.get("effect_size"):
            return False, f"{mech.get('id')}-missing-effect"
        if not mech.get("baseline"):
            return False, f"{mech.get('id')}-missing-baseline"
        if mech.get("promotes_condition") and str(mech.get("evidence_tier")) in {
            "E1",
            "E2",
        }:
            promoted += 1
            if not (mech.get("doi") or mech.get("arxiv") or mech.get("source_ids")):
                return False, f"{mech.get('id')}-promoting-without-source"
    if promoted < 3:
        return False, f"too-few-promoting-mechanisms n={promoted}"
    uncomfortable = str((doc.get("answer") or {}).get("uncomfortable_case") or "")
    if "one signal" not in uncomfortable.lower():
        return False, "uncomfortable-case-absent"
    return True, f"ok conditions={len(conds)} cross_vendor_only={cross} promoted={promoted}"


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = grade(doc)
    print(f"live_ok={ok} {why}")
    if not ok:
        return fail(why)

    mutant = copy.deepcopy(doc)
    for row in mutant["conditions"]:
        row["cross_vendor_only"] = False
    mok, mwhy = grade(mutant)
    print(f"mutant_drop_cross_vendor_only ok={mok} {mwhy}")
    if mok:
        return fail("mutant-without-cross-vendor-only-accepted")

    mutant2 = copy.deepcopy(doc)
    mutant2["conditions"] = mutant2["conditions"][:1]
    m2ok, m2why = grade(mutant2)
    print(f"mutant_one_condition ok={m2ok} {m2why}")
    if m2ok:
        return fail("mutant-single-condition-accepted")

    print("SUCCESS:RES-0098-probe1 condition-by-condition same-vendor verdicts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
