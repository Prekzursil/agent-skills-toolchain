"""Bipartite incidence matrix and both set differences for WFA-0061."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from extract import (
    extract_from_definition,
    extract_from_self_description,
    unmapped_kinds,
    vocab_ids,
)
from goals import looks_like_bare_id_list, route_gaps
from spotcheck import spot_check

RULE = (
    "stages[].kind mapped through the closed vocabulary; "
    "mechanisms[] and notes are mention, not implementation"
)


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def artifact_mechanisms(
    doc: dict[str, Any],
    kind_map: dict[str, str],
    vids: set[str],
) -> list[str]:
    return extract_from_definition(doc, kind_map, vids)


def build_incidence(
    candidates: list[dict[str, Any]],
    blueprints: list[dict[str, Any]],
    kind_map: dict[str, str],
    vocabulary: list[dict[str, Any]],
) -> dict[str, Any]:
    vids = vocab_ids(vocabulary)
    row_ids = [str(v["id"]) for v in vocabulary]
    arts: list[dict[str, Any]] = []
    for rec in candidates:
        arts.append({**rec, "artifact_class": "candidate"})
    for rec in blueprints:
        arts.append({**rec, "artifact_class": "blueprint"})
    col_ids = [str(a["id"]) for a in arts]
    impl: dict[str, list[str]] = {}
    cells: list[dict[str, Any]] = []
    for art in arts:
        aid = str(art["id"])
        mechs = artifact_mechanisms(art, kind_map, vids)
        impl[aid] = mechs
        mset = set(mechs)
        for mid in row_ids:
            evidenced = mid in mset
            cells.append(
                {
                    "row": mid,
                    "col": aid,
                    "artifact_class": art["artifact_class"],
                    "state": "EVIDENCED" if evidenced else "HONEST-NULL",
                    "rule": RULE,
                }
            )
    cand_ids = {str(c["id"]) for c in candidates}
    bp_ids = {str(b["id"]) for b in blueprints}
    mech_in_cand = {
        mid
        for mid in row_ids
        if any(mid in impl[cid] for cid in cand_ids)
    }
    mech_in_bp = {
        mid
        for mid in row_ids
        if any(mid in impl[bid] for bid in bp_ids)
    }
    uncovered = sorted(mech_in_cand - mech_in_bp)
    empty_bps = sorted(bid for bid in bp_ids if not impl[bid])
    blueprint_only = sorted(mech_in_bp - mech_in_cand)
    return {
        "row_ids": row_ids,
        "col_ids": col_ids,
        "cells": cells,
        "implemented_by": {k: v for k, v in sorted(impl.items())},
        "mechanisms_in_candidates": sorted(mech_in_cand),
        "mechanisms_in_blueprints": sorted(mech_in_bp),
        "uncovered_mechanisms": uncovered,
        "empty_blueprints": empty_bps,
        "blueprint_only_mechanisms": blueprint_only,
        "n_candidates": len(candidates),
        "n_blueprints": len(blueprints),
        "n_cells": len(cells),
        "n_evidenced": sum(1 for c in cells if c["state"] == "EVIDENCED"),
        "n_honest_null": sum(1 for c in cells if c["state"] == "HONEST-NULL"),
    }


def suppress_direction(incidence: dict[str, Any], which: str) -> dict[str, Any]:
    """Both-states mutant: drop one of the two mandatory gap lists."""
    out = copy.deepcopy(incidence)
    if which == "empty_blueprints":
        out["empty_blueprints"] = []
    elif which == "uncovered_mechanisms":
        out["uncovered_mechanisms"] = []
    else:
        raise ValueError(which)
    return out


def both_directions_published(incidence: dict[str, Any]) -> bool:
    return bool(incidence.get("uncovered_mechanisms")) and bool(
        incidence.get("empty_blueprints")
    )


def prose_extractor_empty_blueprints(
    blueprints: list[dict[str, Any]],
    vids: set[str],
) -> list[str]:
    empty: list[str] = []
    for rec in blueprints:
        mechs = extract_from_self_description(rec, vids)
        if not mechs:
            empty.append(str(rec["id"]))
    return sorted(empty)


def compute(
    corpus: dict[str, Any],
    live: dict[str, Any],
    worktree_docs: list[dict[str, Any]],
) -> dict[str, Any]:
    vocabulary = list(corpus.get("vocabulary") or [])
    kind_map = dict(corpus.get("kind_map") or {})
    candidates = list(corpus.get("candidates") or [])
    blueprints = list(corpus.get("blueprints") or [])
    vids = vocab_ids(vocabulary)

    incidence = build_incidence(candidates, blueprints, kind_map, vocabulary)
    spots = spot_check(
        uncovered=incidence["uncovered_mechanisms"],
        empty_blueprints=incidence["empty_blueprints"],
        blueprints=blueprints,
        kind_map=kind_map,
        vocabulary=vocabulary,
        n=10,
    )
    published_uncovered = list(incidence["uncovered_mechanisms"])
    published_empty = list(incidence["empty_blueprints"])
    if spots["extraction_rerun_needed"]:
        # Re-run definition extraction after a failed body check.
        incidence = build_incidence(candidates, blueprints, kind_map, vocabulary)
        failed_uncovered = {
            r["gap_id"]
            for r in spots["rows"]
            if r["direction"] == "uncovered_mechanism" and not r["survived"]
        }
        failed_empty = {
            r["gap_id"]
            for r in spots["rows"]
            if r["direction"] == "empty_blueprint" and not r["survived"]
        }
        published_uncovered = [
            m for m in incidence["uncovered_mechanisms"] if m not in failed_uncovered
        ]
        published_empty = [
            b for b in incidence["empty_blueprints"] if b not in failed_empty
        ]
        incidence["uncovered_mechanisms"] = published_uncovered
        incidence["empty_blueprints"] = published_empty
        spots = spot_check(
            uncovered=published_uncovered,
            empty_blueprints=published_empty,
            blueprints=blueprints,
            kind_map=kind_map,
            vocabulary=vocabulary,
            n=10,
        )

    live_lib = bool((live.get("live_blueprint_library") or {}).get("present"))
    goals = route_gaps(
        published_uncovered,
        published_empty,
        live_library_present=live_lib,
    )

    prose_empty = prose_extractor_empty_blueprints(blueprints, vids)
    planted = "bp.prose-says-empty"
    mention = "bp.mention-only"
    docs_bp = "bp.docs-mention-uncovered"

    worktree_rows = []
    for rec in worktree_docs:
        if not isinstance(rec, dict):
            continue
        mechs = extract_from_definition(rec, kind_map, vids)
        worktree_rows.append(
            {
                "id": rec.get("id") or rec.get("path"),
                "path": rec.get("_path"),
                "mechanisms": mechs,
                "unmapped_kinds": unmapped_kinds(rec, kind_map),
                "empty_of_recognised": len(mechs) == 0,
                "slice": "worktree-observed-not-the-108-library",
            }
        )

    dropped = suppress_direction(incidence, "empty_blueprints")
    return {
        "corpus_id": corpus.get("corpus_id"),
        "corpus_label": corpus.get("label"),
        "extraction_rule": RULE,
        "vocabulary_ids": [str(v["id"]) for v in vocabulary],
        "kind_map": kind_map,
        "incidence": incidence,
        "uncovered_mechanisms": published_uncovered,
        "empty_blueprints": published_empty,
        "both_directions_published": both_directions_published(
            {
                "uncovered_mechanisms": published_uncovered,
                "empty_blueprints": published_empty,
            }
        ),
        "spot_checks": spots,
        "generation_lane_goals": goals,
        "generation_lane_is_typed": not looks_like_bare_id_list(goals),
        "planted_extraction_miss": {
            "id": planted,
            "definition_mechanisms": incidence["implemented_by"].get(planted, []),
            "prose_extractor_lists_as_empty": planted in prose_empty,
            "published_as_empty": planted in published_empty,
        },
        "use_versus_mention": {
            "mention_only_blueprint": mention,
            "mention_only_published_empty": mention in published_empty,
            "docs_mention_uncovered_id": docs_bp,
            "docs_mention_covers_fire_and_forget": (
                "mech.fire-and-forget-dispatch"
                in incidence["implemented_by"].get(docs_bp, [])
            ),
            "fire_and_forget_uncovered": (
                "mech.fire-and-forget-dispatch" in published_uncovered
            ),
        },
        "prose_extractor_empty_blueprints": prose_empty,
        "direction_drop_mutant_empty_list": dropped["empty_blueprints"],
        "direction_drop_mutant_still_has_uncovered": bool(
            dropped["uncovered_mechanisms"]
        ),
        "worktree_observed_extraction": worktree_rows,
        "live": {
            "library_108_enumerated": live.get("library_108_enumerated"),
            "extraction_matrix_enumerated": live.get("extraction_matrix_enumerated"),
            "invented_108_blueprints": live.get("invented_108_blueprints"),
            "catalog_claimed_blueprints": live.get("catalog_claimed_blueprints"),
            "catalog_claimed_candidates": live.get("catalog_claimed_candidates"),
        },
        "namespaces": {
            "mechanism_prefix": "mech.",
            "candidate_prefix": "cand.",
            "blueprint_prefix": "bp.",
            "collision": bool(
                (
                    set(str(v["id"]) for v in vocabulary)
                    & set(str(c["id"]) for c in candidates)
                )
                or (
                    set(str(v["id"]) for v in vocabulary)
                    & set(str(b["id"]) for b in blueprints)
                )
                or (
                    set(str(c["id"]) for c in candidates)
                    & set(str(b["id"]) for b in blueprints)
                )
            ),
            "prefix_ok": all(str(v["id"]).startswith("mech.") for v in vocabulary)
            and all(str(c["id"]).startswith("cand.") for c in candidates)
            and all(str(b["id"]).startswith("bp.") for b in blueprints),
        },
    }


def load_worktree_docs(repo: Path, observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for row in observed:
        rel = str(row.get("path") or "")
        path = repo / rel
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            doc = dict(doc)
            doc["_path"] = rel
            docs.append(doc)
    return docs


def corpus_sha(corpus_path: Path) -> str:
    return _sha_bytes(corpus_path.read_bytes())
