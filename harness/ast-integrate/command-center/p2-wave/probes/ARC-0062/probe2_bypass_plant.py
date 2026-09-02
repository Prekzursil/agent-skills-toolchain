#!/usr/bin/env python3
"""Probe 2: bypass plant + overclaim/anchor/scope review.

Clean hybrid must have zero bypass findings. A synthetic skip-evaluator
path (and a second-grant path) must be caught. REFUTED rows must name
DESIGN vs SENTENCE; dropping defect_locus must fail the checker.
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
from hybrid import SINGLE_EVALUATOR_NODE, hybrid_ids  # noqa: E402
from proof import PLANT_ID, PLANT_SECOND_GRANT_ID, run_proof  # noqa: E402

ART = REPO / "command-center/phase3/A9/SECURITY.json"


def main() -> int:
    proof = run_proof()
    skip = proof["plant_skip"]
    second = proof["plant_second_grant"]
    print(
        json.dumps(
            {
                "clean_bypass_count": proof["clean"]["bypass_count"],
                "plant_skip_caught": skip["caught"],
                "plant_skip_id": skip["plant_id"],
                "plant_second_caught": second["caught"],
                "evaluator_node": SINGLE_EVALUATOR_NODE,
            },
            sort_keys=True,
        )
    )
    if proof["clean"]["bypass_count"] != 0:
        print("FAILED:ARC-0062-probe2 clean hybrid has bypass findings")
        return 1
    if not skip["caught"] or skip["plant_id"] != PLANT_ID:
        print("FAILED:ARC-0062-probe2 skip-evaluator plant not caught")
        return 1
    if not second["caught"] or second["plant_id"] != PLANT_SECOND_GRANT_ID:
        print("FAILED:ARC-0062-probe2 second-grant plant not caught")
        return 1
    if SINGLE_EVALUATOR_NODE in skip["plant_hops"]:
        print("FAILED:ARC-0062-probe2 plant still includes evaluator")
        return 1

    if not ART.is_file():
        print("FAILED:ARC-0062-probe2 SECURITY.json missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS" or "SUCCESS:ARC-0062" not in str(doc.get("sentinel") or ""):
        print("FAILED:ARC-0062-probe2 artifact not SUCCESS:ARC-0062")
        return 1
    if doc.get("unit_id") != "ARC-0062":
        print("FAILED:ARC-0062-probe2 unit_id mismatch")
        return 1

    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:ARC-0062-probe2 overclaim check failed on artifact")
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["claims"]:
        if row.get("verdict") == "REFUTED" and "defect_locus" in row:
            del row["defect_locus"]
            stripped = True
            break
    if not stripped:
        print("FAILED:ARC-0062-probe2 no REFUTED defect_locus to strip")
        return 1
    mok, mwhy = O.check_overclaim(mutant)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:ARC-0062-probe2 mutant without defect_locus was accepted")
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
            print("FAILED:ARC-0062-probe2 unresolved anchor")
            return 1
        kind = str(row.get("kind") or "")
        if kind == "dossier":
            if not rel.startswith("command-center/phase3/"):
                print(f"FAILED:ARC-0062-probe2 dossier kind but path {rel}")
                return 1
            dossier += 1
        elif kind == "live-tree":
            if rel.startswith("command-center/phase3/A9/"):
                print(f"FAILED:ARC-0062-probe2 live-tree kind but A9 artifact path {rel}")
                return 1
            live += 1
        else:
            print(f"FAILED:ARC-0062-probe2 bad evidence kind {kind}")
            return 1
    if dossier < 2 or live < 2:
        print(f"FAILED:ARC-0062-probe2 evidence counts dossier={dossier} live={live}")
        return 1

    art_ids = sorted(str(r.get("id")) for r in (doc.get("entry_paths") or []) if isinstance(r, dict))
    live_ids = sorted(hybrid_ids())
    if art_ids != live_ids:
        print(f"FAILED:ARC-0062-probe2 entry_paths drift art={len(art_ids)} live={len(live_ids)}")
        return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("scope_not_agreement") is not True or reviewer.get("independent") is not True:
        print("FAILED:ARC-0062-probe2 reviewer flags")
        return 1
    second_rev = doc.get("second_reviewer") or {}
    if str(second_rev.get("vendor") or "") != "openai":
        print("FAILED:ARC-0062-probe2 second reviewer is not cross-vendor")
        return 1
    if not str(second_rev.get("added_finding") or "").strip():
        print("FAILED:ARC-0062-probe2 second reviewer added no finding")
        return 1

    print(
        f"plant_skip={skip['caught']} plant_second={second['caught']} "
        f"clean_findings={proof['clean']['bypass_count']}"
    )
    print("SUCCESS:ARC-0062-probe2 bypass plant caught and overclaim/anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
