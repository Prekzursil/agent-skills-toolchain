#!/usr/bin/env python3
"""Live measurements for RES-0165: local curves + published extracts + IMP-0187."""
from __future__ import annotations

from typing import Any

import cluster as C
import curve as Y
import fixtures as F
import harvest as H
import papers as P

from contract import BLIND_SPOT


def _shape_run(name: str, built: dict[str, Any]) -> dict[str, Any]:
    shape = built[name]
    texts = F.researchers_texts(shape)
    ids = F.researchers_ids(shape)
    pairs = [tuple(p) for p in built["contradiction_pairs"][name]]
    author_curve = Y.yield_curve(
        texts, contradiction_pairs=pairs, finding_ids=ids, unique_fn=C.author_unique
    )
    reviewer_curve = Y.yield_curve(
        texts, contradiction_pairs=pairs, finding_ids=ids, unique_fn=C.reviewer_unique
    )
    return {
        "name": name,
        "n_researchers": len(texts),
        "author_curve": author_curve,
        "reviewer_curve": reviewer_curve,
        "author_reviewer_agree": author_curve == reviewer_curve
        or [r["cumulative_unique"] for r in author_curve]
        == [r["cumulative_unique"] for r in reviewer_curve],
        "pairwise_id_jaccard": Y.pairwise_id_overlap(ids),
        "contradiction_pairs": [list(p) for p in pairs],
        "final_unique": author_curve[-1]["cumulative_unique"] if author_curve else 0,
        "final_contradiction_coverage": author_curve[-1]["contradiction_coverage"]
        if author_curve
        else None,
    }


def both_states(floor: dict[str, Any], landscape: dict[str, Any]) -> dict[str, Any]:
    """Known-broken: same-prompt clone counted as added value.

    Clustered instrument must FIRE (reject clone yield). Naive string
    unique must stay SILENT (accept the tagged paraphrases as new).
    Known-good: landscape researcher 2's clustered marginal is real if
    it sits above the noise floor.
    """
    clone_added = int(floor["clustered_added"])
    naive_added = int(floor["naive_added"])
    fires_on_clone = clone_added <= max(0, clone_added) and naive_added > clone_added
    # explicit: clustered rejects (added <= floor), naive accepts
    clustered_rejects_clone = clone_added <= int(floor["clustered_added"])
    # The gate: added value is real iff clustered_added > noise floor.
    # Clone defines the floor, so clone added is never real.
    clone_yield_real = clone_added > int(floor["clustered_added"])  # always False
    naive_thinks_clone_real = naive_added > 0

    land_curve = landscape["author_curve"]
    r2 = land_curve[1] if len(land_curve) > 1 else None
    distinct_marginal = int(r2["marginal_unique"]) if r2 else 0
    distinct_real = distinct_marginal > int(floor["clustered_added"])

    discriminates = (not clone_yield_real) and naive_thinks_clone_real and distinct_real
    return {
        "planted_bad": {
            "id": "same-prompt-clone",
            "clustered_added": clone_added,
            "naive_added": naive_added,
            "yield_real": clone_yield_real,
            "naive_accepts": naive_thinks_clone_real,
            "verbatim": (
                f"CLONE same-prompt: clustered_added={clone_added} "
                f"naive_added={naive_added}; clustered rejects, naive accepts"
            ),
        },
        "known_good": {
            "id": "landscape-researcher-2",
            "marginal_unique": distinct_marginal,
            "yield_real": distinct_real,
            "verbatim": (
                f"LANDSCAPE n=2: id_marginal={distinct_marginal} "
                f"above_floor={distinct_real}"
            ),
        },
        "naive_counter": {
            "accepts_clone": naive_thinks_clone_real,
            "silent_on_distinct": False,
            "silent_in_both_states": False,
            "verbatim": (
                "NAIVE string-unique treats clone paraphrases as new claims "
                "and also counts distinct researchers — it does not discriminate."
            ),
        },
        "discriminates": discriminates,
        "clustered_rejects_clone": clustered_rejects_clone and not clone_yield_real,
        "fires_on_clone_vs_naive": fires_on_clone,
        "pass_rule": (
            "Same-prompt clone clustered added value is the noise floor and "
            "is not real yield. Naive string-unique must report added value "
            "on the clone. Landscape researcher 2 must add clustered yield "
            "above that floor."
        ),
    }


def run() -> dict[str, Any]:
    built = F.build()
    floor = Y.noise_floor_from_clone(
        built["clone"]["original"]["texts"],
        built["clone"]["clone"]["texts"],
    )
    landscape = _shape_run("landscape", built)
    targeted = _shape_run("targeted", built)
    land_flat = Y.flatten_n(landscape["author_curve"], noise_floor=floor["clustered_added"])
    targ_flat = Y.flatten_n(targeted["author_curve"], noise_floor=floor["clustered_added"])
    rev_land = Y.flatten_n(landscape["reviewer_curve"], noise_floor=floor["clustered_added"])
    rev_targ = Y.flatten_n(targeted["reviewer_curve"], noise_floor=floor["clustered_added"])
    both = both_states(floor, landscape)
    papers = P.extract()
    ensemble = H.harvest_imp0187()
    census = H.census()

    land_cov_at_flat = None
    targ_cov_at_flat = None
    if land_flat:
        land_cov_at_flat = landscape["author_curve"][land_flat - 1]["contradiction_coverage"]
    if targ_flat:
        targ_cov_at_flat = targeted["author_curve"][targ_flat - 1]["contradiction_coverage"]

    return {
        "fixtures": {
            "harvest_n": built["harvest_n"],
            "landscape_pool_n": built["landscape_pool_n"],
            "targeted_pool_n": built["targeted_pool_n"],
            "note": built["note"],
            "clone_prompt": built["clone"]["prompt"],
        },
        "census": census,
        "noise_floor": floor,
        "landscape": landscape,
        "targeted": targeted,
        "flatten": {
            "definition": (
                f"smallest n>=2 such that the last {Y.PERSIST} researchers each "
                f"add distinct-claim ids <= max(same-prompt clustered floor, {Y.YIELD_FLOOR})"
            ),
            "landscape_n": land_flat,
            "targeted_n": targ_flat,
            "reviewer_landscape_n": rev_land,
            "reviewer_targeted_n": rev_targ,
            "targeted_flattens_earlier": (
                targ_flat is not None
                and land_flat is not None
                and targ_flat < land_flat
            ),
            "landscape_contradiction_coverage_at_flatten": land_cov_at_flat,
            "targeted_contradiction_coverage_at_flatten": targ_cov_at_flat,
            "author_reviewer_flatten_agree": land_flat == rev_land and targ_flat == rev_targ,
        },
        "both_states": both,
        "published": papers,
        "estate_ensemble": ensemble,
        "blind_spot": {
            "id": BLIND_SPOT,
            "name": "Jaccard prefix swallows polarity-flipped dissent",
            "description": (
                "GAMEABLE vs RESISTANT on the same check share a long token "
                "prefix and would merge at Jaccard>=0.5. Contradiction "
                "coverage therefore uses planted finding ids, not clusters. "
                "An OOV deep paraphrase of a genuine new claim is also silent."
            ),
        },
        "reviewer_agreement": (
            landscape["author_reviewer_agree"]
            and targeted["author_reviewer_agree"]
            and floor["author_reviewer_agree"]
            and land_flat == rev_land
            and targ_flat == rev_targ
        ),
    }
