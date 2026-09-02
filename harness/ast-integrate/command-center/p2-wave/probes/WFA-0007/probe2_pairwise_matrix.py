#!/usr/bin/env python3
"""Probe 2: full pairwise Jaccard matrix and both-states reviewer re-run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lexical_scan as LS  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0007-lexical-duplicate-scan.json"
SENTINEL = "SUCCESS:WFA-0007"


def main() -> int:
    corpus = LS.load_corpus()
    rows = corpus["rows"]
    planted = LS.planted_control(rows, LS.THRESHOLD)
    if not planted["planted"]["pass"] or not planted["negative_control"]["pass"]:
        print("FAILED:WFA-0007-probe2 reviewer both-states control")
        return 1
    matrix = LS.pairwise_matrix(rows, LS.THRESHOLD)
    collapse = LS.collapse_records(rows, matrix["above_threshold"])
    matrix_path = LS.write_matrix(matrix)
    print(
        f"PAIRWISE n={matrix['n']} scored_pair_count={matrix['scored_pair_count']}"
    )
    print(f"THRESHOLD {LS.THRESHOLD}")
    print(f"ABOVE_THRESHOLD_COUNT {matrix['above_threshold_count']}")
    for pair in matrix["above_threshold"]:
        print(
            f"ABOVE|{pair['a']}|{pair['b']}|score={pair['score']}|"
            f"{pair['a_name']}|{pair['b_name']}"
        )
    print(f"SURVIVOR_COUNT {collapse['survivor_count']}")
    print(f"REAL_COLLAPSE {collapse['real_collapse']}")
    rw = planted["full_rewrite"]
    print(
        f"FULL_REWRITE missed_by_lexical={rw['missed_by_lexical']} "
        f"score={rw['score_vs_parent']}"
    )
    if matrix["scored_pair_count"] != matrix["expected_pair_count"]:
        print("FAILED:WFA-0007-probe2 pair-count mismatch")
        return 1
    if corpus["n"] == LS.EXPECTED_N and matrix["scored_pair_count"] != 40186:
        print("FAILED:WFA-0007-probe2 expected C(284,2)=40186")
        return 1
    if not collapse["union_preserved"]:
        print("FAILED:WFA-0007-probe2 collapse union lost")
        return 1
    if not rw["missed_by_lexical"]:
        print("FAILED:WFA-0007-probe2 full-rewrite was not missed by lexical")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0007-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:WFA-0007-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:WFA-0007-probe2 artifact self-declared not delivering")
        return 1
    scope = str(doc.get("scope") or "")
    if "LEXICAL" not in scope or "WFA-0008" not in scope:
        print("FAILED:WFA-0007-probe2 lexical scope / WFA-0008 settling missing")
        return 1
    summary = {
        "probe": "probe2-pairwise-matrix",
        "corpus_kind": corpus["kind"],
        "scored_pair_count": matrix["scored_pair_count"],
        "above_threshold_count": matrix["above_threshold_count"],
        "survivor_count": collapse["survivor_count"],
        "matrix_path": LS.MATRIX_REL,
        "reviewer_reran_both_states": True,
        "matrix_bytes": matrix_path.stat().st_size,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:WFA-0007-probe2 pairwise-jaccard-matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
