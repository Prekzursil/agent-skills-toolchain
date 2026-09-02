#!/usr/bin/env python3
"""Probe 2: terminal-state return points, overclaim, reviewer-added mode.

Every dispatch/_checked return must call terminal(). Dropping defect_locus
on a REFUTED claim must make the overclaim checker fail. Reviewer added
FM-JOB-RECEIPT-TEXT and must not certify the unread 47-class list.
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
import returns as R  # noqa: E402

ART = REPO / "command-center/phase3/A6/FAILURE-MODES.json"


def main() -> int:
    live = R.live_report()
    print(
        f"return_points={live['return_point_count']} "
        f"terminal_ok={live['why']} "
        f"mutant_caught={live['mutant_unmarked_caught']}"
    )
    if not live.get("pass"):
        print(f"FAILED:ARC-0040-probe2 return-points {live['why']}")
        return 1
    for row in live["return_points"]:
        print(f"  {row['function']}:{row['lineno']} via_terminal={row['via_terminal']}")
        if not row["via_terminal"]:
            print("FAILED:ARC-0040-probe2 unmarked return")
            return 1

    if not ART.is_file():
        print("FAILED:ARC-0040-probe2 FAILURE-MODES.json missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0040-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0040-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0040-probe2 mutant without defect_locus was accepted")
        return 1

    evidence = doc.get("evidence") or []
    dossier = 0
    live_n = 0
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        rok, rwhy = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={rok} {rwhy}")
        if not rok:
            print("FAILED:ARC-0040-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live_n += 1
        else:
            print(f"FAILED:ARC-0040-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 1 or live_n < 1:
        print(f"FAILED:ARC-0040-probe2 evidence counts dossier={dossier} live={live_n}")
        return 1

    art_ret = doc.get("return_points") or {}
    if int(art_ret.get("return_point_count") or 0) != int(live["return_point_count"]):
        print("FAILED:ARC-0040-probe2 return_point_count drift")
        return 1
    if art_ret.get("mutant_unmarked_caught") is not True:
        print("FAILED:ARC-0040-probe2 artifact did not record mutant catch")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True or rev.get("scope_not_agreement") is not True:
        print("FAILED:ARC-0040-probe2 reviewer is not independent scope-only")
        return 1
    if rev.get("enumeration_certified_against_47") is True:
        print("FAILED:ARC-0040-probe2 cannot certify 47 classes; source file absent")
        return 1
    added = rev.get("added_failure_mode") or {}
    if added.get("id") != "FM-JOB-RECEIPT-TEXT":
        print("FAILED:ARC-0040-probe2 reviewer did not add FM-JOB-RECEIPT-TEXT")
        return 1
    author_ids = {m.get("id") for m in (doc.get("author_failure_modes") or [])}
    if "FM-JOB-RECEIPT-TEXT" in author_ids:
        print("FAILED:ARC-0040-probe2 added mode was already in the author list")
        return 1
    if added.get("caught_by_background_flag") is True:
        print("FAILED:ARC-0040-probe2 job-receipt-text must not be claimed caught by the flag guard")
        return 1

    if "SUCCESS:ARC-0040" not in text:
        print("FAILED:ARC-0040-probe2 sentinel absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ARC-0040-probe2 self-declared {doc.get('state')}")
        return 1
    print("SUCCESS:ARC-0040-probe2 terminals overclaim reviewer-added-mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
