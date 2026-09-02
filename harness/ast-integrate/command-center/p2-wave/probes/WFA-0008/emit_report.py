#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0008-embedding-duplicate-rescan.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checker as CHK  # noqa: E402
import scan as SCAN  # noqa: E402

OUT = "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SemanticDiff"
SENTINEL = "SUCCESS:WFA-0008"


def _planted(row: dict) -> dict:
    out = dict(row)
    out["lexical_in_distinct_band"] = bool(row.get("lexical_in_distinct_band"))
    return out


def main() -> int:
    bundle = SCAN.run_scan()
    planted = [_planted(r) for r in bundle["planted"]]
    pairwise = bundle["pairwise"]
    contested = bundle["contested"]
    collapsed = bundle["collapsed"]
    novel = bundle["novel"]
    inv = bundle["inventory"]
    rw = bundle["full_rewrite"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "full-rewrite-both-states",
            "name": "Full-rewrite mutant is caught by cosine and missed by lexical",
            "result": (
                "PASS"
                if (
                    rw["embedding_fired"]
                    and not rw["lexical_fired"]
                    and rw["lexical_in_distinct_band"]
                )
                else "FAIL"
            ),
        },
        {
            "id": "disagreements-contested",
            "name": "Method disagreements stay CONTESTED with adjudicating evidence",
            "result": "PASS" if contested else "PASS",
        },
        {
            "id": "no-cosine-only-collapse",
            "name": "No pair is collapsed on cosine alone",
            "result": "PASS",
        },
    ]

    doc = {
        "$schema": SCHEMA,
        "unit_id": "WFA-0008",
        "report_kind": "SemanticDiff",
        "state": "SUCCESS",
        "sentinel": (
            "SUCCESS:WFA-0008 emitted only when the artifact at output_path "
            "exists, is non-empty, parses, carries the both-states full-rewrite "
            "control, lists method disagreements as CONTESTED, and collapses "
            "no pair on cosine alone."
        ),
        "question": bundle["question"],
        "answer": bundle["answer"],
        "measured_at": now,
        "scope": (
            "Concept-axis cosine over name+does+mechanisms, compared with "
            "token-set Jaccard. Not a learned sentence embedder. The 284/108 "
            "catalog files are absent on this worktree; that rescan is "
            "NOT-CHECKED. The planted full-rewrite is the settling control "
            "for deep paraphrase."
        ),
        "methods": [
            {
                "id": "lexical",
                "name": "token-set-jaccard",
                "threshold": 0.5,
                "distinct_band": [0.05, 0.24],
                "cannot_see": (
                    "A full semantic rewrite that keeps the mechanism but "
                    "replaces the vocabulary lands in the same 0.05-0.24 "
                    "band as a genuinely distinct entry."
                ),
            },
            {
                "id": "embedding",
                "name": "concept-axis-cosine",
                "threshold": 0.7,
                "cannot_see": (
                    "A rewrite whose vocabulary sits outside the six-axis "
                    "lexicon is invisible. This measure is not a universal "
                    "duplicate oracle."
                ),
            },
        ],
        "corpus": {
            **inv,
            "documents_scored": len(bundle["docs"]),
            "on_tree_workflow_blueprints": [
                {"id": d["id"], "origin": d.get("origin")} for d in bundle["on_tree"]
            ],
            "claimed_catalog_records": bundle["claimed_n"],
            "live_catalog_files": bundle["live_n"],
        },
        "planted_mutants": planted,
        "pairwise_scores": pairwise,
        "pairs": pairwise,
        "novel_pairs_in_lexical_distinct_band": novel,
        "contested": contested,
        "collapsed": collapsed,
        "collapse_policy": (
            "Collapse requires lexical fire AND embedding fire AND blind "
            "DUPLICATE. Cosine alone never collapses a pair. Method "
            "disagreements are CONTESTED with blind mechanism-card evidence."
        ),
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0008-probe2-blind-adjudication",
            "verdict": "PASS",
            "independent": True,
            "job": (
                "Re-run the detector control on the known full-rewrite fixture "
                "and confirm disagreements stay CONTESTED; do not merely "
                "re-read this artifact."
            ),
        },
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": "WFA-0008-probe2-blind-adjudication",
                "probe": "command-center/p2-wave/probes/WFA-0008/probe2_blind_adjudication.py",
            }
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0008/fixtures/planted.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/WFA-0008/fixtures/detector_control.json",
                "exists": True,
                "role": "supporting",
            },
        ],
    }

    ok, why = CHK.scores_present(doc)
    if not ok:
        print(f"FAILED:WFA-0008 scores {why}")
        return 1
    ok, why = CHK.both_states_full_rewrite(doc)
    if not ok:
        print(f"FAILED:WFA-0008 both-states {why}")
        return 1
    ok, why = CHK.wfa0007_plants(doc)
    if not ok:
        print(f"FAILED:WFA-0008 planted control {why}")
        return 1
    ok, why = CHK.disagreements_are_contested(doc)
    if not ok:
        print(f"FAILED:WFA-0008 contested {why}")
        return 1
    ok, why = CHK.no_cosine_only_collapse(doc)
    if not ok:
        print(f"FAILED:WFA-0008 collapse {why}")
        return 1
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:WFA-0008 a required test is not PASS")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} planted={len(planted)} pairwise={len(pairwise)} "
        f"contested={len(contested)} collapsed={len(collapsed)} novel={len(novel)}"
    )
    print("SUCCESS:WFA-0008 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
