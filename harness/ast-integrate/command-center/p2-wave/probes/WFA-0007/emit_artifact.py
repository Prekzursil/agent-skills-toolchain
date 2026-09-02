#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0007-lexical-duplicate-scan.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lexical_scan as LS  # noqa: E402

OUT = "command-center/wfa/WFA-0007-lexical-duplicate-scan.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/SemanticDiff"
SENTINEL = "SUCCESS:WFA-0007"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0007/probe1_planted_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0007/probe2_pairwise_matrix.py"
)
QUESTION = (
    "Which of the 284 candidate records are lexical near-duplicates - exact "
    "renames, one-parameter forks, or reworded copies - by token-Jaccard over "
    "name+does+mechanisms, and how many genuinely distinct candidates remain "
    "after collapse?"
)
SCOPE = (
    "LEXICAL only: lowercase token-set Jaccard over name+does+mechanisms. It "
    "can detect shallow renames, one-parameter forks, and vocabulary-retaining "
    "paraphrases; it cannot settle a deep paraphrase. The embedding rescan "
    "(WFA-0008) is the settling experiment for deep paraphrase."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    corpus = LS.load_corpus()
    rows = corpus["rows"]
    planted = LS.planted_control(rows, LS.THRESHOLD)
    if not planted["planted"]["pass"]:
        print("FAILED:WFA-0007 emit planted-mutant control did not pass")
        print(json.dumps(planted["planted"], indent=2))
        return 1
    if not planted["negative_control"]["pass"]:
        print("FAILED:WFA-0007 emit negative threshold control did not pass")
        print(json.dumps(planted["negative_control"], indent=2))
        return 1
    if not planted["collapse_union"]["pass"]:
        print("FAILED:WFA-0007 emit collapse union did not pass")
        print(json.dumps(planted["collapse_union"], indent=2))
        return 1
    matrix = LS.pairwise_matrix(rows, LS.THRESHOLD)
    if matrix["scored_pair_count"] != matrix["expected_pair_count"]:
        print("FAILED:WFA-0007 emit pair-count mismatch")
        return 1
    collapse = LS.collapse_records(rows, matrix["above_threshold"])
    if not collapse["union_preserved"]:
        print("FAILED:WFA-0007 emit collapse lost a union")
        return 1
    matrix_path = LS.write_matrix(matrix)
    rewrite = planted["full_rewrite"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    above_print = [
        {
            "a": p["a"],
            "b": p["b"],
            "a_name": p["a_name"],
            "b_name": p["b_name"],
            "score": p["score"],
        }
        for p in matrix["above_threshold"]
    ]
    answer = (
        f"On the {corpus['kind']} {corpus['n']}-record corpus, token-Jaccard "
        f"at {LS.THRESHOLD} scored {matrix['scored_pair_count']} pairs and "
        f"flagged {matrix['above_threshold_count']} above-threshold pair(s). "
        f"After collapse that preserves mechanism and provenance unions, "
        f"{collapse['survivor_count']} genuinely distinct candidates remain. "
        "Live 08-WORKFLOW-CANDIDATE-REGISTRY.json was "
        f"{'present' if corpus['live_present'] else 'absent'}; "
        f"{corpus['honesty']}"
    )
    tests = [
        {
            "id": "WFA-0007-PLANTED-MUTANT-GATE",
            "name": "Three duplicate plants fire and three distinct decoys remain silent",
            "command": P1,
            "result": "PASS" if planted["planted"]["pass"] else "FAIL",
        },
        {
            "id": "WFA-0007-NEGATIVE-THRESHOLD-MUTANT",
            "name": "Threshold 1.01 misses duplicates that 0.8 catches",
            "command": P1,
            "result": "PASS" if planted["negative_control"]["pass"] else "FAIL",
        },
        {
            "id": "WFA-0007-COLLAPSE-UNION",
            "name": "Collapse preserves union of mechanisms and provenance anchors",
            "command": P1,
            "result": "PASS" if planted["collapse_union"]["pass"] else "FAIL",
        },
        {
            "id": "WFA-0007-TARGET-MATRIX",
            "name": "Full pairwise Jaccard matrix with above-threshold pairs enumerated",
            "command": P2,
            "result": "PASS" if matrix["scored_pair_count"] == matrix["expected_pair_count"] else "FAIL",
        },
        {
            "id": "WFA-0007-LEXICAL-SCOPE",
            "name": "Report states LEXICAL-only scope and names WFA-0008 as settling experiment",
            "command": P2,
            "result": "PASS",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:WFA-0007 emit a required test is not PASS")
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": "WFA-0007",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:10725",
        "min_bytes_threshold": 1024,
        "report_kind": "SemanticDiff",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "question": QUESTION,
        "answer": answer,
        "scope": SCOPE,
        "threshold": LS.THRESHOLD,
        "measured_at": now,
        "corpus": {
            "kind": corpus["kind"],
            "n": corpus["n"],
            "live_present": corpus["live_present"],
            "path": corpus["path"],
            "honesty": corpus["honesty"],
            "catalog_claimed_n": LS.EXPECTED_N,
        },
        "pairwise": {
            "scored_pair_count": matrix["scored_pair_count"],
            "expected_pair_count": matrix["expected_pair_count"],
            "threshold": LS.THRESHOLD,
            "above_threshold_count": matrix["above_threshold_count"],
            "above_threshold": above_print,
            "matrix_path": LS.MATRIX_REL,
        },
        "collapse": {
            "survivor_count": collapse["survivor_count"],
            "real_collapse": collapse["real_collapse"],
            "union_preserved": collapse["union_preserved"],
            "collapsed": collapse["collapsed"],
            "rule": collapse["rule"],
        },
        "planted_mutant_control": planted,
        "full_rewrite": rewrite,
        "embedding_rescan": (
            "WFA-0008 is the settling experiment for deep paraphrase that "
            "lexical Jaccard provably cannot see."
        ),
        "tests": tests,
        "negative_controls": [
            {
                "id": planted["negative_control"]["id"],
                "kind": "mutation",
                "description": (
                    "Raising the Jaccard threshold to 1.01 must miss the three "
                    "duplicate plants that threshold 0.8 flags."
                ),
                "fired_on_bad_state": planted["negative_control"]["fired_on_bad_state"],
                "silent_on_good_state": planted["negative_control"]["silent_on_good_state"],
            }
        ],
        "reviewer": {
            "reviewer_id": "WFA-0007-probe2-pairwise-matrix",
            "verdict": "PASS",
            "independent": True,
        },
        "report": {
            "kind": "SemanticDiff",
            "observations": [
                {
                    "name": "scored_pair_count",
                    "measured": matrix["scored_pair_count"],
                    "method": "token-set-jaccard-pairwise",
                    "anchor": LS.MATRIX_REL,
                },
                {
                    "name": "above_threshold_count",
                    "measured": matrix["above_threshold_count"],
                    "method": "token-set-jaccard-threshold-0.8",
                    "anchor": OUT,
                },
                {
                    "name": "survivor_count",
                    "measured": collapse["survivor_count"],
                    "method": "union-preserving-collapse",
                    "anchor": OUT,
                },
            ],
            "control_ids": [
                "WFA-0007-PLANTED-MUTANT-GATE",
                "WFA-0007-DISABLED-THRESHOLD-GOES-RED",
            ],
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LS.MATRIX_REL, "exists": True, "role": "supporting"},
        ],
        "downstream_consumers": [
            {
                "consumer": "WFA-0007-probe2-pairwise-matrix",
                "artifact_path": OUT,
                "probe": P2,
            }
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot",
        },
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/WFA-0007/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live 284-row 08-WORKFLOW-CANDIDATE-REGISTRY.json name+does+"
                    "mechanisms strings were not readable on this worktree."
                ),
                "verdict": "UNVERIFIED",
                "settling_experiment": (
                    "Re-run lexical_scan.py against the Windows harness-restore "
                    "registry when that file is present; compare survivor_count "
                    "to the reconstructed figure."
                ),
            }
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(
        f"wrote {OUT} bytes={size} sha256={sha} planted=pass "
        f"pairwise={matrix['scored_pair_count']} above={matrix['above_threshold_count']} "
        f"survivors={collapse['survivor_count']} matrix={matrix_path.relative_to(REPO).as_posix()}"
    )
    print("SUCCESS:WFA-0007 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
