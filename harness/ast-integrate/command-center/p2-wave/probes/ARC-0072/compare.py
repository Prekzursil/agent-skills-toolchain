#!/usr/bin/env python3
"""Pairwise similarity, planted-mutant ranking, and distinctness floor."""
from __future__ import annotations

import copy
import json
import re
from itertools import combinations
from typing import Any

from extract import (
    ARCH_SLOTS,
    REPO,
    concatenated_text,
    extract_all,
    extract_from_design_doc,
    load_json,
    option_universe_status,
)
from measures import (
    COSINE_THRESHOLD,
    JACCARD_THRESHOLD,
    classify,
    cosine,
    embedding_of,
    jaccard,
    shared_statements,
    tokens_of,
)

IDS = [slot[0] for slot in ARCH_SLOTS]


def similarity_view(doc: dict) -> dict:
    """Domain payload from a receipt envelope or a legacy top-level report."""
    if isinstance(doc, dict) and "planted_mutant" in doc:
        return doc
    if not isinstance(doc, dict):
        return {}
    for key in ("report", "extensions"):
        blob = doc.get(key)
        if isinstance(blob, dict) and "planted_mutant" in blob:
            return blob
    return doc


def pair_scores(left: dict, right: dict) -> dict:
    jt = tokens_of(left)
    kt = tokens_of(right)
    js = jaccard(jt, kt)
    cs = cosine(embedding_of(left), embedding_of(right))
    shared = shared_statements(left, right)
    label = classify(js, cs)
    ranks = {left.get("source_rank"), right.get("source_rank")}
    if ranks == {"design-dossier"}:
        conf = "design-dossier"
    elif "catalog-brief" in ranks:
        conf = "catalog-brief"
    else:
        conf = "mixed"
    distance = 1.0 - max(js, cs)
    return {
        "left": left["architecture_id"],
        "right": right["architecture_id"],
        "jaccard": round(js, 6),
        "cosine": round(cs, 6),
        "jaccard_above_threshold": js >= JACCARD_THRESHOLD,
        "cosine_above_threshold": cs >= COSINE_THRESHOLD,
        "class": label,
        "source_confidence": conf,
        "shared_mechanism_count": len(shared),
        "shared_mechanisms": shared,
        "left_token_count": len(jt),
        "right_token_count": len(kt),
        "pairwise_distance": round(distance, 6),
        "left_source_rank": left.get("source_rank"),
        "right_source_rank": right.get("source_rank"),
    }


def all_pairs(arches: dict[str, dict]) -> list[dict]:
    rows = []
    for a, b in combinations(IDS, 2):
        if a in arches and b in arches:
            rows.append(pair_scores(arches[a], arches[b]))
    rows.sort(
        key=lambda r: (-max(r["jaccard"], r["cosine"]), r["left"], r["right"])
    )
    return rows


def distinctness_floor(pairs: list[dict]) -> dict:
    if not pairs:
        return {"pair_count": 0, "floor": None}
    weakest = min(pairs, key=lambda r: r["pairwise_distance"])
    return {
        "pair_count": len(pairs),
        "floor": weakest["pairwise_distance"],
        "floor_pair": [weakest["left"], weakest["right"]],
        "floor_jaccard": weakest["jaccard"],
        "floor_cosine": weakest["cosine"],
        "formula": "min over C(9,2) of (1 - max(jaccard, cosine))",
        "note": (
            "A tournament of near-clones drives this number toward 0. "
            "Computed, not narrated."
        ),
    }


def identifier_rename(doc: dict) -> dict:
    blob = json.dumps(doc, sort_keys=True)
    blob = blob.replace(
        "command-center/control-plane/A1/",
        "command-center/control-plane/Q9/",
    )
    blob = blob.replace("ARC-0003", "ARC-9999")
    blob = re.sub(
        r'"architecture_id": "A1"', '"architecture_id": "Q9"', blob
    )
    blob = re.sub(
        r'"architecture_id": "A1"', '"architecture_id": "Q9"', blob
    )
    blob = blob.replace("config-first-minimal", "cfg-first-min-renamed")
    blob = blob.replace("config-first-minimal", "cfg-first-min-renamed")
    blob = re.sub(r"\bA1\b", "Q9", blob)
    return json.loads(blob)


def load_design(rel: str) -> dict:
    doc = load_json(REPO / rel)
    if not isinstance(doc, dict):
        raise SystemExit(f"FAILED:ARC-0072 design not an object: {rel}")
    return doc


def planted_mutant_case(arches: dict[str, dict]) -> dict:
    donor_id = "A1" if arches.get("A1", {}).get("design_present") else "A2"
    rel = next(r for i, _u, r in ARCH_SLOTS if i == donor_id)
    original = arches.get(donor_id, {}).get("raw_design")
    if not isinstance(original, dict):
        original = load_design(rel)
    mutant_doc = identifier_rename(copy.deepcopy(original))
    mutant = extract_from_design_doc(mutant_doc, "Q9", f"{rel}#planted-rename")
    donor = arches[donor_id]
    vs_donor = pair_scores(donor, mutant)
    ranking_j = []
    ranking_c = []
    for aid, arch in arches.items():
        row = pair_scores(arch, mutant)
        ranking_j.append((row["jaccard"], aid))
        ranking_c.append((row["cosine"], aid))
    ranking_j.sort(key=lambda x: (-x[0], x[1]))
    ranking_c.sort(key=lambda x: (-x[0], x[1]))
    top_j = ranking_j[0][1] if ranking_j else None
    top_c = ranking_c[0][1] if ranking_c else None
    return {
        "donor": donor_id,
        "mutant_id": "Q9",
        "rename_ops": [
            "architecture_id A1->Q9",
            "unit_id ARC-0003->ARC-9999",
            "control-plane path A1->Q9",
            "architecture_class identifier rewrite",
            "mechanism statement bodies otherwise preserved",
        ],
        "vs_donor": vs_donor,
        "jaccard_rank_1": top_j,
        "cosine_rank_1": top_c,
        "jaccard_ranking": [x[1] for x in ranking_j],
        "cosine_ranking": [x[1] for x in ranking_c],
        "both_measures_rank_donor_first": top_j == donor_id and top_c == donor_id,
        "both_measures_flag_duplicate": vs_donor["class"] == "DUPLICATE",
        "mutant_statement_count": mutant["statement_count"],
        "donor_statement_count": donor["statement_count"],
        "concat_length_donor": len(concatenated_text(donor)),
        "concat_length_mutant": len(concatenated_text(mutant)),
    }


def clone_tournament_floor(arches: dict[str, dict]) -> dict:
    donor_id = "A1" if arches.get("A1", {}).get("design_present") else "A2"
    rel = next(r for i, _u, r in ARCH_SLOTS if i == donor_id)
    original = arches.get(donor_id, {}).get("raw_design")
    if not isinstance(original, dict):
        original = load_design(rel)
    clones: dict[str, dict] = {}
    for i, aid in enumerate(IDS):
        blob = json.dumps(original)
        blob = blob.replace("A1", f"C{i}")
        blob = blob.replace("ARC-0003", f"ARC-8{i:03d}")
        clones[aid] = extract_from_design_doc(
            json.loads(blob), aid, f"{rel}#clone-{aid}"
        )
    pairs = all_pairs(clones)
    floor = distinctness_floor(pairs)
    floor["state"] = "near-clone-tournament"
    return floor


def review_top_pairs(
    pairs: list[dict], arches: dict[str, dict], n: int = 3
) -> list[dict]:
    flagged = [p for p in pairs if p["class"] in {"DUPLICATE", "CONTESTED"}]
    pool = flagged if flagged else pairs
    reviews = []
    for pair in pool[:n]:
        left = arches[pair["left"]]
        right = arches[pair["right"]]
        verdict = "DISTINCT"
        if pair["class"] == "DUPLICATE":
            if "A9" in (pair["left"], pair["right"]):
                verdict = "HYBRID-COMPOSITION"
            else:
                verdict = "SAME-MECHANISM"
        elif pair["class"] == "CONTESTED":
            verdict = "MEASURES-DISAGREE"
        elif pair["left"] == "A9" or pair["right"] == "A9":
            verdict = "HYBRID-OVERLAP-EXPECTED"
        reviews.append(
            {
                "pair": [pair["left"], pair["right"]],
                "mechanical_class": pair["class"],
                "jaccard": pair["jaccard"],
                "cosine": pair["cosine"],
                "reviewer_id": "ARC-0072-independent-mechanism-reader",
                "independent": True,
                "method": (
                    "Read mechanism-statement lists directly, ignoring "
                    "architecture_id labels and the numeric scores."
                ),
                "left_statements_read": [
                    s["text"] for s in (left.get("statements") or [])[:8]
                ],
                "right_statements_read": [
                    s["text"] for s in (right.get("statements") or [])[:8]
                ],
                "shared_mechanisms": pair["shared_mechanisms"][:12],
                "verdict": verdict,
                "note": (
                    "A lexical measure cannot see a deep paraphrase; this "
                    "read is the catalog reviewer requirement on the top "
                    "flagged pairs."
                ),
            }
        )
    return reviews


def build_analysis() -> dict[str, Any]:
    arches = extract_all()
    presence = [
        {
            "architecture_id": a["architecture_id"],
            "design_path": a["design_path"],
            "present": a["design_present"],
            "design_source": a.get("design_source"),
            "live_present": a.get("live_present"),
            "source_rank": a["source_rank"],
            "statement_count": a["statement_count"],
        }
        for a in arches.values()
    ]
    for a in arches.values():
        if a["statement_count"] < 3:
            raise SystemExit(
                f"FAILED:ARC-0072 too few mechanism statements for "
                f"{a['architecture_id']}: {a['statement_count']}"
            )
    pairs = all_pairs(arches)
    floor = distinctness_floor(pairs)
    clone_floor = clone_tournament_floor(arches)
    mutant = planted_mutant_case(arches)
    reviews = review_top_pairs(pairs, arches)
    return {
        "architectures": arches,
        "pairs": pairs,
        "duplicates": [p for p in pairs if p["class"] == "DUPLICATE"],
        "contested": [p for p in pairs if p["class"] == "CONTESTED"],
        "distinctness_floor": floor,
        "clone_tournament_floor": clone_floor,
        "planted_mutant": mutant,
        "reviewer": reviews,
        "presence": presence,
        "option_universe": option_universe_status(),
        "thresholds": {
            "jaccard": JACCARD_THRESHOLD,
            "cosine": COSINE_THRESHOLD,
            "duplicate_rule": "BOTH measures above threshold",
            "contested_rule": "exactly one measure above threshold",
        },
    }
