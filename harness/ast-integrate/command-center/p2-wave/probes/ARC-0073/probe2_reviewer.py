#!/usr/bin/env python3
"""Probe 2: independent reviewer + overclaim + evidence anchors."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import live as L  # noqa: E402
import overclaim as O  # noqa: E402
import parser as P  # noqa: E402
import reviewer as R  # noqa: E402

ART = REPO / "command-center/phase3/CONTROL-PLANE-SINGULARITY.json"
SAMPLED = ("skill.council", "wf.catalog-class.discovery-only")


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0073-probe2 CONTROL-PLANE-SINGULARITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    live = L.report(REPO)
    ok, why = O.check_overclaim(doc, live)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0073-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["computed_not_prose"] = False
    mok, mwhy = O.check_overclaim(mutant, live)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0073-probe2 mutant without computed_not_prose was accepted")
        return 1

    subject = L.reviewer_subject(REPO)
    print(f"reviewer_subject={subject['source']} path={subject['path']}")
    parsed = P.evaluate(subject["doc"])
    for cap in SAMPLED:
        row = R.match_parser(subject["doc"], parsed["rows"], cap)
        print(
            f"reviewer {cap} match={row['match']} "
            f"hand={row['hand_paths']} parser={row['parser_paths']}"
        )
        if not row["match"]:
            print(f"FAILED:ARC-0073-probe2 reviewer mismatch {cap}")
            return 1

    recorded = doc.get("reviewer_replication") or []
    rec_by_id = {r.get("capability_id"): r for r in recorded if isinstance(r, dict)}
    for cap in SAMPLED:
        rec = rec_by_id.get(cap) or {}
        if not rec.get("match"):
            print(f"FAILED:ARC-0073-probe2 artifact reviewer row missing/fail {cap}")
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
            print("FAILED:ARC-0073-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            dossier += 1
        elif kind == "live-tree":
            live_n += 1
        else:
            print(f"FAILED:ARC-0073-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 1 or live_n < 1:
        print(f"FAILED:ARC-0073-probe2 evidence counts dossier={dossier} live={live_n}")
        return 1

    if doc.get("prose_accepted_as_evidence") is True:
        print("FAILED:ARC-0073-probe2 prose accepted")
        return 1
    if not doc.get("computed_not_prose"):
        print("FAILED:ARC-0073-probe2 computed_not_prose missing")
        return 1
    print("SUCCESS:ARC-0073-probe2 reviewer overclaim anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
