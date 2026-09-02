"""Measure the detection envelope on the planted corpus."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import methods as M  # noqa: E402


def measure() -> dict[str, Any]:
    recs = C.records()
    rows: list[dict[str, Any]] = []
    for pair in C.pairs():
        left = recs[pair["left"]]
        right = recs[pair["right"]]
        cmp = M.compare(left, right)
        rows.append(
            {
                "shape": pair["shape"],
                "left_id": left["id"],
                "right_id": right["id"],
                "semantic_duplicate": pair["semantic_duplicate"],
                "settling_experiment": pair["settling_experiment"],
                "lexical_hit": cmp["lexical-jaccard"]["hit"],
                "lexical_score": cmp["lexical-jaccard"]["score"],
                "embedding_hit": cmp["embedding-expanded-token-jaccard"]["hit"],
                "embedding_score": cmp["embedding-expanded-token-jaccard"]["score"],
                "structural_hit": cmp["structural-ir-sets"]["hit"],
                "combined_hit": cmp["combined_hit"],
                "methods": {
                    "lexical-jaccard": cmp["lexical-jaccard"],
                    "embedding-expanded-token-jaccard": cmp[
                        "embedding-expanded-token-jaccard"
                    ],
                    "structural-ir-sets": cmp["structural-ir-sets"],
                },
            }
        )

    detects = sorted(
        {
            r["shape"]
            for r in rows
            if r["semantic_duplicate"] and r["combined_hit"]
        }
    )
    undetectable = []
    for r in rows:
        if r["semantic_duplicate"] and not r["combined_hit"]:
            undetectable.append(
                {
                    "id": r["shape"],
                    "left_id": r["left_id"],
                    "right_id": r["right_id"],
                    "lexical_hit": r["lexical_hit"],
                    "embedding_hit": r["embedding_hit"],
                    "structural_hit": r["structural_hit"],
                    "settling_experiment": r["settling_experiment"],
                }
            )
    decoys_silent = [
        r["shape"]
        for r in rows
        if (not r["semantic_duplicate"]) and (not r["combined_hit"])
    ]
    decoy_false_positives = [
        r["shape"]
        for r in rows
        if (not r["semantic_duplicate"]) and r["combined_hit"]
    ]
    return {
        "methods": list(M.METHOD_IDS),
        "thresholds": {
            "lexical_jaccard": M.LEXICAL_THRESHOLD,
            "embedding_expanded_jaccard": M.EMBEDDING_THRESHOLD,
            "structural": "five-set-equality-nonempty",
        },
        "embedding_stand_in": {
            "method_id": "embedding-expanded-token-jaccard",
            "neural_artifact": "command-center/wfa/WFA-0008-embedding-duplicate-rescan.json",
            "neural_artifact_present": False,
            "label": "UNVERIFIED",
            "note": (
                "WFA-0008 neural embedding artifact is ABSENT; the embedding-class "
                "column is frozen synonym-expanded token Jaccard, not a neural cosine."
            ),
        },
        "rows": rows,
        "detects": detects,
        "undetectable_classes": undetectable,
        "decoys_silent": decoys_silent,
        "decoy_false_positives": decoy_false_positives,
        "counts": {
            "pairs": len(rows),
            "semantic_duplicates": sum(1 for r in rows if r["semantic_duplicate"]),
            "combined_hits": sum(1 for r in rows if r["combined_hit"]),
            "undetectable": len(undetectable),
            "decoy_false_positives": len(decoy_false_positives),
        },
    }


def canonical_scope(measured: dict[str, Any] | None = None) -> dict[str, Any]:
    env = measured if measured is not None else measure()
    misses = []
    for row in env["undetectable_classes"]:
        misses.append(
            {
                "id": row["id"],
                "settling_experiment": row["settling_experiment"],
            }
        )
    return {
        "envelope_id": "WFA-0097-DUP-SCOPE-v1",
        "kind": "duplicate-detection-envelope",
        "methods": list(env["methods"]),
        "detects": list(env["detects"]),
        "does_not_detect": misses,
        "thresholds": env["thresholds"],
        "embedding_stand_in": env["embedding_stand_in"]["method_id"],
        "corpus": "planted-mutant-control",
    }
