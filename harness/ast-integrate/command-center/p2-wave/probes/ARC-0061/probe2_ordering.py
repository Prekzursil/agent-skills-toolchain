#!/usr/bin/env python3
"""Probe 2: ordering enumeration, overclaim, reviewer-added mode, anchors."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anchors as A  # noqa: E402
import ordering as ORD  # noqa: E402
import overclaim as O  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center/phase3/A9/FAILURE-MODES.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0061-probe2 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    problems = ORD.assert_complete()
    if problems:
        print("FAILED:ARC-0061-probe2 ordering source", problems)
        return 1
    listed = doc.get("ordering_constraints") or []
    if not isinstance(listed, list) or len(listed) < 8:
        print("FAILED:ARC-0061-probe2 ordering list short")
        return 1
    src_ids = [c["id"] for c in ORD.constraints()]
    art_ids = [c.get("id") for c in listed]
    if art_ids != src_ids:
        print("FAILED:ARC-0061-probe2 ordering id drift")
        return 1
    for row in listed:
        why = ORD.validate_row(row)
        if why:
            print(f"FAILED:ARC-0061-probe2 {row.get('id')} {why}")
            return 1
    print(f"ordering_ok=True n={len(listed)}")

    ok, why = O.check_overclaim(doc, REPO)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0061-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0061-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant, REPO)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0061-probe2 mutant without defect_locus was accepted")
        return 1

    evidence = doc.get("evidence") or []
    dossier = 0
    live = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0061-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live += 1
        else:
            print(f"FAILED:ARC-0061-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 1 or live < 1:
        print(f"FAILED:ARC-0061-probe2 evidence counts dossier={dossier} live={live}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0061-probe2 reviewer is not independent scope-only")
        return 1
    if rev.get("enumeration_certified_against_47") is True:
        print("FAILED:ARC-0061-probe2 cannot certify 47 classes; source file absent")
        return 1
    added = rev.get("added_failure_mode") or {}
    if added.get("id") != "FM-AUTHORITY-STRING-COLLISION":
        print("FAILED:ARC-0061-probe2 reviewer did not add FM-AUTHORITY-STRING-COLLISION")
        return 1
    author_ids = {m.get("id") for m in (doc.get("author_failure_modes") or [])}
    if "FM-AUTHORITY-STRING-COLLISION" in author_ids:
        print("FAILED:ARC-0061-probe2 added mode was already in the author list")
        return 1

    if doc.get("detector_control", {}).get("a9_design_present") is True:
        print("FAILED:ARC-0061-probe2 overclaim A9 DESIGN present")
        return 1
    if "SUCCESS:ARC-0061" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0061-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0061-probe2 ordering overclaim reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
