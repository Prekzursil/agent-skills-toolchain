#!/usr/bin/env python3
"""Probe 2: overclaim check + independent scope review of anchors.

Every REFUTED verdict must state DESIGN vs SENTENCE. A correctly scoped
claim is CONFIRMED. Dropping defect_locus from a REFUTED row must make
the checker fail. Anchors must resolve on disk (3 dossier + 1 live-tree).
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
import overclaim as O  # noqa: E402

ART = REPO / "command-center/phase3/A1/REFUTATION.json"
DOSSIER_PREFIX = "command-center/phase3/A1/"


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0009-probe2 REFUTATION.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0009-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0009-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0009-probe2 mutant without defect_locus was accepted")
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
            print("FAILED:ARC-0009-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            if not rel.startswith(DOSSIER_PREFIX):
                print(f"FAILED:ARC-0009-probe2 dossier kind but path {rel}")
                return 1
            dossier += 1
        elif kind == "live-tree":
            if rel.startswith(DOSSIER_PREFIX):
                print(f"FAILED:ARC-0009-probe2 live-tree kind but dossier path {rel}")
                return 1
            live += 1
        else:
            print(f"FAILED:ARC-0009-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 3 or live < 1:
        print(f"FAILED:ARC-0009-probe2 evidence counts dossier={dossier} live={live}")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0009-probe2 reviewer is not independent scope-only")
        return 1
    if "SUCCESS:ARC-0009" not in ART.read_text(encoding="utf-8"):
        print("FAILED:ARC-0009-probe2 sentinel absent")
        return 1
    print("SUCCESS:ARC-0009-probe2 overclaim and anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
