#!/usr/bin/env python3
"""Shared live measurements for RES-0084 emit + probes.

A probe that is silent in both states measures nothing: the gate must
FIRE on the 100-variant gamed corpus (unique < 100) and stay SILENT on
the 100-distinct corpus (unique >= 100). Both runs are recorded.
"""
from __future__ import annotations

from typing import Any

import counter as C
import fixtures as F


FLOOR = 100


def _pairwise_jaccard(ideas: list[str], *, fold: bool) -> dict[str, float]:
    n = len(ideas)
    toks = [C.content_tokens(s, fold_synonyms=fold) for s in ideas]
    lo = 1.0
    hi = 0.0
    total = 0.0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            val = C.jaccard(toks[i], toks[j])
            lo = min(lo, val)
            hi = max(hi, val)
            total += val
            pairs += 1
    return {
        "n_pairs": pairs,
        "min": round(lo, 6) if pairs else 0.0,
        "max": round(hi, 6) if pairs else 0.0,
        "mean": round(total / pairs, 6) if pairs else 0.0,
    }


def _band_pair(a: str, b: str) -> dict[str, Any]:
    raw_a = C.content_tokens(a, fold_synonyms=False)
    raw_b = C.content_tokens(b, fold_synonyms=False)
    fold_a = C.content_tokens(a, fold_synonyms=True)
    fold_b = C.content_tokens(b, fold_synonyms=True)
    return {
        "left": a,
        "right": b,
        "raw_jaccard": round(C.jaccard(raw_a, raw_b), 6),
        "folded_jaccard": round(C.jaccard(fold_a, fold_b), 6),
        "raw_tokens_left": list(raw_a),
        "raw_tokens_right": list(raw_b),
        "folded_key_left": list(C.mechanism_key(a)),
        "folded_key_right": list(C.mechanism_key(b)),
        "keys_equal": C.mechanism_key(a) == C.mechanism_key(b),
    }


def _corpus_run(name: str, ideas: list[str], threshold: float) -> dict[str, Any]:
    author = C.unique_count_union_find(ideas, threshold)
    reviewer = C.unique_count_connected_components(ideas, threshold)
    j_only = C.unique_count_jaccard_only(ideas, threshold)
    k_only = C.unique_count_keys_only(ideas)
    naive = C.naive_unique(ideas)
    return {
        "name": name,
        "n_strings": len(ideas),
        "naive_unique": naive,
        "author_union_find": author,
        "reviewer_connected_components": reviewer,
        "jaccard_only": j_only,
        "keys_only": k_only,
        "gate_accepts_100": C.gate_unique_ge(author, FLOOR),
        "threshold": threshold,
    }


def run() -> dict[str, Any]:
    gamed = F.gamed_corpus(100)
    distinct = F.distinct_corpus()

    gamed_fold = _pairwise_jaccard(gamed, fold=True)
    gamed_raw = _pairwise_jaccard(gamed, fold=False)
    dist_fold = _pairwise_jaccard(distinct, fold=True)
    dist_raw = _pairwise_jaccard(distinct, fold=False)

    # Rename band: min folded Jaccard among gamed pairs. Distinct band:
    # max folded Jaccard among distinct pairs. Threshold sits in the gap
    # when one exists.
    threshold, thresh_rule = C.choose_threshold(gamed_fold["min"], dist_fold["max"])

    gamed_run = _corpus_run("known-broken-gamed-100", gamed, threshold)
    distinct_run = _corpus_run("known-good-distinct-100", distinct, threshold)

    # Both-states of the uniqueness GATE (FIRE = reject 100-unique).
    fires_on_gamed = gamed_run["author_union_find"] < FLOOR
    silent_on_distinct = distinct_run["author_union_find"] >= FLOOR
    naive_silent_on_gamed = gamed_run["naive_unique"] >= FLOOR
    naive_silent_on_distinct = distinct_run["naive_unique"] >= FLOOR

    seed_vs_gamed0 = _band_pair(F.SEED, gamed[0])
    rename_pair = _band_pair(gamed[0], gamed[1])
    deep = _band_pair(F.SEED, F.DEEP_PARAPHRASE)
    distinct_ctrl = _band_pair(F.SEED, F.DISTINCT_CONTROL)

    ladder = F.adversarial_ladder(F.SEED)
    at_or_above = [s for s in ladder if s["jaccard_vs_seed"] >= threshold]
    below = [s for s in ladder if s["jaccard_vs_seed"] < threshold]
    last_above = at_or_above[-1] if at_or_above else None
    first_below = below[0] if below else None

    # Survival at the threshold: the last at-or-above pair must merge
    # with the seed under S1 (Jaccard-only unique count of [seed, text] == 1).
    threshold_pair_merges = None
    if last_above is not None:
        threshold_pair_merges = (
            C.unique_count_jaccard_only([F.SEED, last_above["text"]], threshold) == 1
        )

    # Deep paraphrase vs genuine distinct: both should sit below threshold
    # with unequal keys — the lexical metric cannot split them.
    same_band = (
        deep["folded_jaccard"] < threshold
        and distinct_ctrl["folded_jaccard"] < threshold
        and not deep["keys_equal"]
        and not distinct_ctrl["keys_equal"]
    )
    deep_counted_distinct = (
        C.unique_count_union_find([F.SEED, F.DEEP_PARAPHRASE], threshold) == 2
    )
    ctrl_counted_distinct = (
        C.unique_count_union_find([F.SEED, F.DISTINCT_CONTROL], threshold) == 2
    )

    return {
        "floor": FLOOR,
        "measured_threshold": threshold,
        "threshold_selection": thresh_rule,
        "candidate_threshold": C.CANDIDATE_THRESHOLD,
        "pairwise": {
            "gamed_folded": gamed_fold,
            "gamed_raw": gamed_raw,
            "distinct_folded": dist_fold,
            "distinct_raw": dist_raw,
        },
        "known_broken": {
            "ideas": gamed,
            "run": gamed_run,
        },
        "known_good": {
            "ideas": distinct,
            "run": distinct_run,
        },
        "both_states": {
            "planted_bad": {
                "fixture": "100 trivial rewordings of one cache-family mechanism",
                "unique_count": gamed_run["author_union_find"],
                "gate_accepts_100": gamed_run["gate_accepts_100"],
                "observed": "FIRE" if fires_on_gamed else "SILENT",
                "want": "FIRE",
                "verbatim": (
                    f"gamed n={len(gamed)} naive={gamed_run['naive_unique']} "
                    f"author={gamed_run['author_union_find']} "
                    f"reviewer={gamed_run['reviewer_connected_components']} "
                    f"jaccard_only={gamed_run['jaccard_only']} "
                    f"keys_only={gamed_run['keys_only']} "
                    f"gate_accepts_100={gamed_run['gate_accepts_100']}"
                ),
                "passed": fires_on_gamed,
            },
            "known_good": {
                "fixture": "100 genuinely distinct mechanisms",
                "unique_count": distinct_run["author_union_find"],
                "gate_accepts_100": distinct_run["gate_accepts_100"],
                "observed": "SILENT" if silent_on_distinct else "FIRE",
                "want": "SILENT",
                "verbatim": (
                    f"distinct n={len(distinct)} naive={distinct_run['naive_unique']} "
                    f"author={distinct_run['author_union_find']} "
                    f"reviewer={distinct_run['reviewer_connected_components']} "
                    f"jaccard_only={distinct_run['jaccard_only']} "
                    f"keys_only={distinct_run['keys_only']} "
                    f"gate_accepts_100={distinct_run['gate_accepts_100']}"
                ),
                "passed": silent_on_distinct,
            },
            "naive_counter": {
                "gamed_accepts_100": naive_silent_on_gamed,
                "distinct_accepts_100": naive_silent_on_distinct,
                "silent_in_both_states": naive_silent_on_gamed and naive_silent_on_distinct,
                "verbatim": (
                    f"naive unique gamed={gamed_run['naive_unique']} "
                    f"distinct={distinct_run['naive_unique']}; "
                    "string-equality accepts the gamed 100 and the distinct 100, "
                    "so it measures nothing"
                ),
            },
            "discriminates": fires_on_gamed and silent_on_distinct,
        },
        "lexical_bands": {
            "seed_vs_first_gamed": seed_vs_gamed0,
            "two_gamed_variants": rename_pair,
            "deep_paraphrase": deep,
            "genuine_distinct_control": distinct_ctrl,
            "rename_paraphrase_band_note": (
                "Lexical (raw) Jaccard fires on synonym-close rewordings and "
                "renames; a full rewrite lands in the same low band as a "
                "genuinely distinct idea."
            ),
        },
        "adversarial_generator": {
            "seed": F.SEED,
            "ladder": ladder,
            "last_at_or_above_threshold": last_above,
            "first_below_threshold": first_below,
            "at_threshold_pair_merges_under_S1": threshold_pair_merges,
            "survives_at_threshold": threshold_pair_merges is True,
            "note": (
                "The generator walks nonce replacements until folded Jaccard "
                "crosses the measured threshold. Survival means the last pair "
                "still at-or-above threshold is merged by S1. Pairs below the "
                "threshold that remain synonym-equivalent still merge via S2; "
                "OOV rewrites below the threshold are the named blind spot."
            ),
        },
        "blind_spot": {
            "id": "RES-0084-DEEP-PARAPHRASE-BAND",
            "name": "deep paraphrase / OOV full rewrite",
            "description": (
                "A lexical Jaccard metric fires on renames and light paraphrases "
                "but a full rewrite that leaves the synonym table lands in the "
                "same low-Jaccard, unequal-key band as a genuinely distinct idea. "
                "S2 only catches rewrites that fold onto the same canonical key."
            ),
            "settling_experiment": {
                "id": "RES-0084-DEEP-PARAPHRASE-BAND",
                "procedure": (
                    "Measure folded Jaccard and key equality for (SEED, DEEP_PARAPHRASE) "
                    "and (SEED, DISTINCT_CONTROL). If both pairs are below threshold "
                    "with unequal keys, and the counter reports unique_count=2 for "
                    "each pair, the metric cannot separate a successful deep "
                    "paraphrase of the SAME idea from a genuinely different idea."
                ),
                "deep_paraphrase_pair": deep,
                "distinct_control_pair": distinct_ctrl,
                "same_lexical_band": same_band,
                "deep_pair_unique_count": 2 if deep_counted_distinct else 1,
                "control_pair_unique_count": 2 if ctrl_counted_distinct else 1,
                "third_signal_not_shipped": (
                    "Closing this band requires a third signal (embedding cosine "
                    "or NLI entailment) which this unit does not ship."
                ),
            },
            "stated_inline": True,
        },
        "reviewer_agreement": gamed_run["author_union_find"]
        == gamed_run["reviewer_connected_components"]
        and distinct_run["author_union_find"]
        == distinct_run["reviewer_connected_components"],
        "seed": F.SEED,
        "deep_paraphrase": F.DEEP_PARAPHRASE,
        "distinct_control": F.DISTINCT_CONTROL,
    }
