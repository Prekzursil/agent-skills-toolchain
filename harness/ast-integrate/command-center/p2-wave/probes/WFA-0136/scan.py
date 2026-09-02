"""Pairwise lexical + semantic scan with planted-mutant control."""
from __future__ import annotations

from typing import Any

import catalog as C
import detector as D
import planted as P


def _score_pair(a: dict, b: dict, idf: dict[str, float], n_docs: int) -> dict:
    pa, pb = C.prose_of(a), C.prose_of(b)
    jac = D.jaccard(pa, pb)
    cos = D.cosine(
        D.embed(pa, str(a.get("mechanism") or ""), idf, n_docs),
        D.embed(pb, str(b.get("mechanism") or ""), idf, n_docs),
    )
    return {
        "a": a["id"],
        "b": b["id"],
        "jaccard": jac,
        "cosine": cos,
    }


def run_scan(entries: list[dict]) -> dict[str, Any]:
    if len(entries) < C.FLOOR:
        raise ValueError(f"catalog has {len(entries)} entries, floor is {C.FLOOR}")
    by_id = {e["id"]: e for e in entries}
    if P.ANCHOR_ID not in by_id:
        raise ValueError(f"anchor {P.ANCHOR_ID} missing from catalog")
    anchor = by_id[P.ANCHOR_ID]
    para, dist = P.plants_from_anchor(anchor)
    n_docs = len(entries)
    idf = D.fit_idf(C.prose_of(e) for e in entries)

    para_s = _score_pair(anchor, para, idf, n_docs)
    dist_s = _score_pair(anchor, dist, idf, n_docs)
    cal = D.calibrate_thresholds(
        para_s["cosine"], dist_s["cosine"], para_s["jaccard"]
    )
    if not cal.get("ok"):
        return {
            "ok": False,
            "reason": cal.get("reason"),
            "calibration": cal,
            "planted": {"paraphrase": para_s, "distinct": dist_s},
            "n_entries": len(entries),
        }

    cos_th = float(cal["cosine_threshold"])
    jac_th = float(cal["jaccard_threshold"])
    para_s["lexical_flag"] = D.lexical_flag(para_s["jaccard"], jac_th)
    para_s["semantic_flag"] = D.semantic_flag(para_s["cosine"], cos_th)
    dist_s["lexical_flag"] = D.lexical_flag(dist_s["jaccard"], jac_th)
    dist_s["semantic_flag"] = D.semantic_flag(dist_s["cosine"], cos_th)

    detector_ok = para_s["semantic_flag"] and not dist_s["semantic_flag"]
    jaccard_as_detector_broken = (not para_s["lexical_flag"]) and (
        not dist_s["lexical_flag"]
    )

    pairs: list[dict] = []
    max_cos = 0.0
    max_jac = 0.0
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            row = _score_pair(a, b, idf, n_docs)
            row["lexical_flag"] = D.lexical_flag(row["jaccard"], jac_th)
            row["semantic_flag"] = D.semantic_flag(row["cosine"], cos_th)
            max_cos = max(max_cos, row["cosine"])
            max_jac = max(max_jac, row["jaccard"])
            pairs.append(row)

    lexical_flags = [r for r in pairs if r["lexical_flag"]]
    semantic_flags = [r for r in pairs if r["semantic_flag"]]
    cosine_near_jaccard_distinct = [
        r for r in pairs if r["semantic_flag"] and not r["lexical_flag"]
    ]
    nearest = sorted(pairs, key=lambda r: r["cosine"], reverse=True)[:8]

    nadb_counts = {
        "mechanism-difference": 0,
        "wording-only": 0,
        "unclassified": 0,
        "absent": 0,
    }
    for e in entries:
        nadb_counts[D.nadb_kind(str(e.get("not_a_duplicate_because") or ""))] += 1

    survivors = []
    for row in cosine_near_jaccard_distinct:
        a, b = by_id[row["a"]], by_id[row["b"]]
        ka = D.nadb_kind(str(a.get("not_a_duplicate_because") or ""))
        kb = D.nadb_kind(str(b.get("not_a_duplicate_because") or ""))
        survivors.append(
            {
                **row,
                "a_nadb": str(a.get("not_a_duplicate_because") or ""),
                "b_nadb": str(b.get("not_a_duplicate_because") or ""),
                "a_nadb_kind": ka,
                "b_nadb_kind": kb,
                "mechanism_difference_named": (
                    ka == "mechanism-difference" or kb == "mechanism-difference"
                ),
            }
        )

    return {
        "ok": True,
        "detector_ok": detector_ok,
        "jaccard_as_semantic_detector_broken": jaccard_as_detector_broken,
        "n_entries": len(entries),
        "n_pairs": len(pairs),
        "idf_documents": n_docs,
        "calibration": cal,
        "cosine_threshold": cos_th,
        "jaccard_threshold": jac_th,
        "planted": {
            "paraphrase": {**para_s, "id": P.PARAPHRASE_ID, "anchor_id": P.ANCHOR_ID},
            "distinct": {**dist_s, "id": P.DISTINCT_ID, "anchor_id": P.ANCHOR_ID},
            "verdict": "PASS" if detector_ok else "BROKEN",
        },
        "max_cosine": max_cos,
        "max_jaccard": max_jac,
        "lexical_flags": lexical_flags,
        "semantic_flags": semantic_flags,
        "cosine_near_jaccard_distinct": cosine_near_jaccard_distinct,
        "nearest_neighbors": nearest,
        "nadb_counts": nadb_counts,
        "survivors": survivors,
        "pairs": pairs,
    }
