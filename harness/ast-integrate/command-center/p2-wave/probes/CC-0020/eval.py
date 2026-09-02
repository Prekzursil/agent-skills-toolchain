"""Shared scoring for CC-0020 probes and the receipt emitter."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from corpus import DISTINCT_24, SEED_A_ID, SEED_B_ID, fifth_mutants, planted, seeds
from gate import compare, compare_records, error_direction, false_merge, record_text
from load_catalog import by_id

CLASSES = ("exact-rename", "paraphrase", "one-parameter-fork", "full-rewrite")


def score_planted() -> dict[str, Any]:
    rows = planted()
    seed_map = {s["id"]: s for s in seeds()}
    by_cls: dict[str, list[dict[str, Any]]] = defaultdict(list)
    misses: list[dict[str, Any]] = []
    for rec in rows:
        cls = rec["mutant_class"]
        if cls == "seed":
            continue
        gold = seed_map[rec["gold_same_as"]]
        cmp = compare(record_text(gold), record_text(rec))
        cmp.update(
            {
                "mutant_id": rec["id"],
                "seed_id": gold["id"],
                "mutant_class": cls,
                "error_direction": error_direction(True, cmp["verdict"]),
            }
        )
        by_cls[cls].append(cmp)
        if not cmp["caught"]:
            misses.append(cmp)
    per_class = {}
    for cls in CLASSES:
        items = by_cls.get(cls, [])
        n = len(items)
        n_caught = sum(1 for x in items if x["caught"])
        per_class[cls] = {
            "n": n,
            "caught": n_caught,
            "rate": (n_caught / n) if n else 0.0,
            "jaccard": [x["jaccard"] for x in items],
            "cosine": [x["cosine"] for x in items],
            "verdicts": [x["verdict"] for x in items],
            "rows": items,
        }
    cross = compare(record_text(seed_map[SEED_A_ID]), record_text(seed_map[SEED_B_ID]))
    cross["error_direction"] = error_direction(False, cross["verdict"])
    return {
        "per_class": per_class,
        "misses": misses,
        "all_four_caught": all(per_class[c]["caught"] == per_class[c]["n"] and per_class[c]["n"] > 0 for c in CLASSES),
        "cross_seed": cross,
        "cross_seed_not_merged": not false_merge(cross["verdict"]),
    }


def score_distinct() -> dict[str, Any]:
    idx = by_id()
    recs = []
    missing = []
    for row in DISTINCT_24:
        u = idx.get(row["id"])
        if not u:
            missing.append(row["id"])
            continue
        recs.append(
            {
                "id": row["id"],
                "because": row["because"],
                "title": u.get("title"),
                "text": record_text(u),
            }
        )
    pairs = []
    merges = []
    over_flags = []
    max_j = 0.0
    max_c = 0.0
    for i, a in enumerate(recs):
        for b in recs[i + 1 :]:
            cmp = compare_records(a, b)
            cmp["left_because"] = a["because"]
            cmp["right_because"] = b["because"]
            cmp["error_direction"] = error_direction(False, cmp["verdict"])
            pairs.append(cmp)
            max_j = max(max_j, cmp["jaccard"])
            max_c = max(max_c, cmp["cosine"])
            if false_merge(cmp["verdict"]):
                merges.append(cmp)
            if cmp["verdict"] == "ADJUDICATE":
                over_flags.append(cmp)
    return {
        "n_units": len(recs),
        "n_pairs": len(pairs),
        "missing_ids": missing,
        "false_merge_count": len(merges),
        "adjudicate_count": len(over_flags),
        "max_jaccard": round(max_j, 6),
        "max_cosine": round(max_c, 6),
        "merges": merges,
        "adjudications": over_flags,
        "units": [{"id": r["id"], "because": r["because"], "title": r["title"]} for r in recs],
    }


def score_fifth() -> dict[str, Any]:
    seed = next(s for s in seeds() if s["id"] == SEED_A_ID)
    fifth = fifth_mutants()[0]
    cmp = compare(record_text(seed), record_text(fifth))
    cmp.update(
        {
            "mutant_id": fifth["id"],
            "mutant_class": fifth["mutant_class"],
            "error_direction": error_direction(True, cmp["verdict"]),
            "thresholds_frozen_before_this_class": True,
        }
    )
    return cmp


def determinism_check(n: int = 3) -> dict[str, Any]:
    payloads = []
    for _ in range(n):
        planted_s = score_planted()
        dist = score_distinct()
        fifth = score_fifth()
        payloads.append(
            {
                "per_class_verdicts": {
                    c: planted_s["per_class"][c]["verdicts"] for c in CLASSES
                },
                "false_merge_count": dist["false_merge_count"],
                "fifth_verdict": fifth["verdict"],
                "fifth_jaccard": fifth["jaccard"],
                "fifth_cosine": fifth["cosine"],
            }
        )
    identical = all(p == payloads[0] for p in payloads[1:])
    return {"runs": n, "identical": identical, "snapshot": payloads[0]}
