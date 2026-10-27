#!/usr/bin/env python3
"""Probe 2: overclaim, anchors, reviewer-added FM-EXCEPT-PASS.

Every REFUTED claim names DESIGN vs SENTENCE. Dropping defect_locus must
make the checker fail. Evidence anchors resolve. Reviewer added a failure
mode the author missed. A7 DESIGN remains absent. Combined 'all gates
pass' is forbidden.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import events as E  # noqa: E402
import gates as G  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/phase3/A7/FAILURE-MODES.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0047-probe2 FAILURE-MODES.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0047-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0047-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0047-probe2 mutant without defect_locus was accepted")
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
            print("FAILED:ARC-0047-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live += 1
        else:
            print(f"FAILED:ARC-0047-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 1 or live < 1:
        print(f"FAILED:ARC-0047-probe2 evidence counts dossier={dossier} live={live}")
        return 1

    _d7 = REPO / "command-center/phase3/A7/DESIGN.json"
    if bool(doc.get("a7_design_present")) != _d7.is_file():
        print("FAILED:ARC-0047-probe2 a7_design_present disagrees with tree")
        return 1
    if _d7.is_file() and _d7.stat().st_mtime > Path(__file__).stat().st_mtime:
        print("FAILED:ARC-0047-probe2 A7 DESIGN.json rebuilt during this wave")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0047-probe2 reviewer is not independent scope-only")
        return 1
    if rev.get("enumeration_certified_against_47") is True:
        print("FAILED:ARC-0047-probe2 cannot certify 47 classes; source file absent")
        return 1
    added = rev.get("added_failure_mode") or {}
    if added.get("id") != "FM-EXCEPT-PASS":
        print("FAILED:ARC-0047-probe2 reviewer did not add FM-EXCEPT-PASS")
        return 1
    author_ids = {m.get("id") for m in (doc.get("author_failure_modes") or [])}
    if "FM-EXCEPT-PASS" in author_ids:
        print("FAILED:ARC-0047-probe2 added mode was already in the author list")
        return 1
    if G.except_pass_gate(E.EXCEPT_ON_USE) is not False:
        print("FAILED:ARC-0047-probe2 FM-EXCEPT-PASS not mechanically fail-open")
        return 1
    if G.except_pass_gate(E.USE_BASH) is not True:
        print("FAILED:ARC-0047-probe2 except-pass without error should defer to verb gate")
        return 1

    audit = doc.get("gate_audit") or {}
    if "combined_pass_count" in audit or "all_gates_pass" in audit:
        print("FAILED:ARC-0047-probe2 combined pass count forbidden")
        return 1

    if "SUCCESS:ARC-0047" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0047-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0047-probe2 overclaim anchors reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
