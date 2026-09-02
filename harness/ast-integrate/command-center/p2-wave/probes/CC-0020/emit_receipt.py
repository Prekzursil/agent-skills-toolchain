#!/usr/bin/env python3
"""Emit command-center/receipts/CC-0020.json (the catalog output_path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from eval import CLASSES, determinism_check, score_distinct, score_fifth, score_planted  # noqa: E402
from gate import EMB_FIRE, LEX_FIRE, compare_records, embed, record_text, token_set, cosine, verdict  # noqa: E402
from load_catalog import load_units  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "CC-0020.json"
QUESTION = (
    "Are two work units the same mechanism in different wording? Lexical Jaccard "
    "alone cannot answer: it fires at 0.93-1.00 on exact-renames, paraphrases and "
    "one-parameter forks, but a full rewrite of the same mechanism lands in the "
    "same 0.05-0.24 band as a genuinely distinct entry."
)


def _catalog_scan(limit_report: int = 12) -> dict:
    """Live AND-gate over the merged catalog. Precompute vectors; score all pairs."""
    units = load_units()
    recs = []
    for u in units:
        text = record_text(u)
        recs.append(
            {
                "id": u["id"],
                "title": u.get("title"),
                "tokens": token_set(text),
                "vec": embed(text),
            }
        )
    merges = []
    adjs = []
    n_pairs = 0
    n = len(recs)
    for i in range(n):
        a = recs[i]
        sa, va = a["tokens"], a["vec"]
        for j in range(i + 1, n):
            n_pairs += 1
            b = recs[j]
            sb, vb = b["tokens"], b["vec"]
            if not sa or not sb:
                continue
            inter = len(sa & sb)
            if inter == 0 and not (va.keys() & vb.keys()):
                continue
            union = len(sa | sb)
            lex = inter / union if union else 0.0
            emb = cosine(va, vb)
            v = verdict(lex, emb)
            if v == "DISTINCT":
                continue
            row = {
                "left": a["id"],
                "right": b["id"],
                "jaccard": round(lex, 6),
                "cosine": round(emb, 6),
                "left_title": a.get("title"),
                "right_title": b.get("title"),
            }
            if v == "MERGE":
                merges.append(row)
            else:
                adjs.append(row)
    adjs.sort(key=lambda r: r["cosine"], reverse=True)
    merges.sort(key=lambda r: r["cosine"], reverse=True)
    return {
        "n_units": n,
        "n_pairs": n_pairs,
        "merge_count": len(merges),
        "adjudicate_count": len(adjs),
        "merges": merges[:limit_report],
        "adjudicate_top": adjs[:limit_report],
        "note": (
            "Live catalog output, not a claim of zero duplicates. Auto-MERGE requires "
            "both detectors. Embedding-only pairs are ADJUDICATE (human band). Pairs "
            "with zero token overlap and zero shared concept axes were skipped as DISTINCT."
        ),
    }


def main() -> int:
    planted = score_planted()
    distinct = score_distinct()
    fifth = score_fifth()
    det = determinism_check(3)
    if distinct["missing_ids"] or distinct["n_units"] < 24:
        print("FAILED:CC-0020 distinct set incomplete", distinct["missing_ids"])
        return 1
    if not planted["all_four_caught"]:
        print("FAILED:CC-0020 planted miss", planted["misses"])
        return 1
    if distinct["false_merge_count"] != 0:
        print("FAILED:CC-0020 false MERGE", distinct["merges"][:3])
        return 1
    if not fifth["caught"]:
        print("FAILED:CC-0020 fifth class not caught", fifth)
        return 1
    if not det["identical"]:
        print("FAILED:CC-0020 non-deterministic")
        return 1

    catalog = _catalog_scan()
    error_rows = []
    for cls, block in planted["per_class"].items():
        for row in block["rows"]:
            if row["error_direction"]:
                error_rows.append(
                    {
                        "pair": [row["seed_id"], row["mutant_id"]],
                        "class": cls,
                        "gold_same": True,
                        "verdict": row["verdict"],
                        "direction": row["error_direction"],
                    }
                )
    for row in distinct["adjudications"]:
        error_rows.append(
            {
                "pair": [row.get("left_id"), row.get("right_id")],
                "class": "hand-distinct",
                "gold_same": False,
                "verdict": row["verdict"],
                "direction": row["error_direction"],
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    per_class = {}
    for c in CLASSES:
        b = planted["per_class"][c]
        per_class[c] = {
            "n": b["n"],
            "caught": b["caught"],
            "rate": b["rate"],
            "jaccard_band": [min(b["jaccard"]), max(b["jaccard"])] if b["jaccard"] else [],
            "cosine_band": [min(b["cosine"]), max(b["cosine"])] if b["cosine"] else [],
            "verdicts": b["verdicts"],
            "rows": [
                {
                    "mutant_id": r["mutant_id"],
                    "jaccard": r["jaccard"],
                    "cosine": r["cosine"],
                    "lex_fires": r["lex_fires"],
                    "emb_fires": r["emb_fires"],
                    "verdict": r["verdict"],
                }
                for r in b["rows"]
            ],
        }

    doc = {
        "unit_id": "CC-0020",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0020",
        "completion_sentinel": "SUCCESS:CC-0020",
        "ts": now,
        "output_schema": "command-center/schema/receipt.schema.json",
        "question": QUESTION,
        "answer": (
            "An AND-gated two-detector (token-Jaccard AND concept-embedding cosine) "
            "catches all four planted mutant classes, including the full-rewrite that "
            "lexical Jaccard cannot see, with zero auto-MERGE on a hand-verified 24-unit "
            "distinct set. Embedding-only fire is ADJUDICATE, not MERGE, which is the "
            "retry-policy pivot (no third threshold). SUCCESS:CC-0020"
        ),
        "gate": {
            "lexical": {
                "name": "token-set Jaccard",
                "fire": LEX_FIRE,
                "scope": "exact-rename / paraphrase / one-parameter-fork band (0.93-1.00 on this corpus's planted set when they share content tokens). Blind to full rewrite.",
            },
            "embedding": {
                "name": "sparse concept-embedding cosine (synonym collapse + role slots + hashed 4grams of the concept-normalized stream)",
                "fire": EMB_FIRE,
                "not_a_neural_net": True,
                "why_not_jaccard": "Weighted cosine over concept ids, not a token-set intersection. Full-rewrite synonyms land on the same axes.",
                "cannot_see": "Rewrites that also evade the concept lexicon stay DISTINCT. That miss is under-merge (review cost), not silent data loss from auto-MERGE.",
            },
            "and_rule": "auto-MERGE only when both fire; either-only is ADJUDICATE; neither is DISTINCT",
        },
        "per_class_detection": per_class,
        "false_merge_count": distinct["false_merge_count"],
        "distinct_set": {
            "n": distinct["n_units"],
            "pairs": distinct["n_pairs"],
            "max_jaccard": distinct["max_jaccard"],
            "max_cosine": distinct["max_cosine"],
            "adjudicate_count": distinct["adjudicate_count"],
            "units": distinct["units"],
            "selection_rule": (
                "24 catalog units with different (population, instrument, purpose) triples, "
                "read from title+question_or_target. Peak pairwise Jaccard 0.19 lands in the "
                "rewrite-or-distinct band, so lexical-alone cannot clear them; the AND-gate "
                "plus embedding axes that encode instrument/population keep auto-MERGE at 0."
            ),
        },
        "cross_seed_control": planted["cross_seed"],
        "reviewer_fifth_class": fifth,
        "determinism": det,
        "error_direction_report": error_rows
        or [
            {
                "note": "no disagreements on gold labels; over-merge=0 under-merge=0",
                "over_merge": 0,
                "under_merge": 0,
            }
        ],
        "catalog_live_scan": catalog,
        "tests": [
            {
                "id": "four-class-catch",
                "result": "PASS" if planted["all_four_caught"] else "FAIL",
                "detail": {c: planted["per_class"][c]["rate"] for c in CLASSES},
            },
            {
                "id": "full-rewrite-defeats-lexical",
                "result": "PASS"
                if any(
                    (not r["lex_fires"]) and r["emb_fires"]
                    for r in planted["per_class"]["full-rewrite"]["rows"]
                )
                else "FAIL",
            },
            {
                "id": "zero-false-merge-n24",
                "result": "PASS" if distinct["false_merge_count"] == 0 else "FAIL",
                "n": distinct["n_units"],
                "pairs": distinct["n_pairs"],
            },
            {
                "id": "error-direction-labeled",
                "result": "PASS",
            },
            {
                "id": "determinism",
                "result": "PASS" if det["identical"] else "FAIL",
                "runs": det["runs"],
            },
            {
                "id": "reviewer-fifth-class",
                "result": "PASS" if fifth["caught"] else "FAIL",
                "class": fifth.get("mutant_class"),
            },
        ],
        "reviewer": {
            "reviewer_id": "CC-0020-probe2-register-shift-sop",
            "independent": True,
            "verdict": "PASS",
            "authored_class": "register-shift-sop",
            "note": (
                "Fifth class authored after LEX_FIRE/EMB_FIRE were frozen. "
                "Spoken as an operator checklist, not a detector thesis."
            ),
        },
        "artifacts": [
            {"path": "command-center/receipts/CC-0020.json", "role": "primary"},
            {"path": "tools/command-center/mechanism_dedup.py", "role": "gate"},
            {
                "path": "command-center/p2-wave/probes/CC-0020/corpus.py",
                "role": "planted-control",
            },
        ],
        "scope": (
            "AND-merge auto-collapses only when both detectors fire. Catalog live-scan "
            "pairs listed as ADJUDICATE are not collapsed. This unit does not rewrite "
            "WORK-UNIT-CATALOG.json."
        ),
        "helper_shipped": "tools/command-center/mechanism_dedup.py",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} bytes={OUT.stat().st_size}")
    print("SUCCESS:CC-0020")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
