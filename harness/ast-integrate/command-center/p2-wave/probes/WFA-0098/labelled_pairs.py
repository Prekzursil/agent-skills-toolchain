#!/usr/bin/env python3
"""Labelled pair set for WFA-0098 duplicate-threshold calibration.

Every pair carries:
  should_collapse          ground-truth collapse decision
  unique_left / unique_right
  two_directional_divergence  True iff BOTH sides hold unique content

Token-set Jaccard is |shared| / (|shared| + |left_only| + |right_only|).
Pair scores are planted so weak paraphrases overlap two-directional-divergence:
a threshold that catches the weak paraphrases also collapses unique-content
pairs. That overlap is the estate trap balanced accuracy falls into.
"""
from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")

SCOPE = (
    "LEXICAL token-set Jaccard over candidate text. A full semantic rewrite "
    "is NOT detectable by this instrument and is labelled should_collapse="
    "true only as a trap: lowering the threshold to catch rewrites collapses "
    "two-directional unique-content pairs (the dangerous error)."
)


def tokenize(text: str) -> frozenset[str]:
    return frozenset(TOKEN_RE.findall((text or "").lower()))


def jaccard(a: str, b: str) -> float:
    left, right = tokenize(a), tokenize(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _word(prefix: str, i: int) -> str:
    return f"{prefix}{i:02d}"


def render(shared: list[str], unique: list[str]) -> str:
    return "candidate text " + " ".join(shared + unique)


def make_pair(
    pid: str,
    label_class: str,
    should_collapse: bool,
    n_shared: int,
    n_unique_each: int,
    shared_prefix: str,
    left_prefix: str,
    right_prefix: str,
) -> dict[str, Any]:
    shared = [_word(shared_prefix, i) for i in range(n_shared)]
    left_u = [_word(left_prefix, i) for i in range(n_unique_each)]
    right_u = [_word(right_prefix, i) for i in range(n_unique_each)]
    left_text = render(shared, left_u)
    right_text = render(shared, right_u)
    tl, tr = tokenize(left_text), tokenize(right_text)
    left_only = sorted(tl - tr)
    right_only = sorted(tr - tl)
    both_unique = bool(left_only) and bool(right_only)
    score = round(jaccard(left_text, right_text), 6)
    return {
        "pair_id": pid,
        "label_class": label_class,
        "should_collapse": should_collapse,
        "two_directional_divergence": label_class == "two_directional_divergence",
        "left_id": f"{pid}-left",
        "right_id": f"{pid}-right",
        "left_text": left_text,
        "right_text": right_text,
        "jaccard": score,
        "unique_left": left_only,
        "unique_right": right_only,
        "shared_count": len(tl & tr),
        "union_count": len(tl | tr),
    }


def labelled_pairs() -> list[dict[str, Any]]:
    """Fixed labelled set. Scores are a function of token sets, not of a stored number."""
    rows: list[dict[str, Any]] = []

    # True duplicates: high Jaccard (identifier / light paraphrase / one-parameter).
    for i, (s, k) in enumerate(((40, 1), (38, 2), (36, 2), (34, 3), (32, 3))):
        rows.append(
            make_pair(
                f"rename-{i:02d}",
                "exact_rename",
                True,
                s,
                k,
                "rnsh",
                "rnla",
                "rnra",
            )
        )
    for i, (s, k) in enumerate(((30, 4), (28, 4), (26, 5))):
        rows.append(
            make_pair(
                f"para-light-{i:02d}",
                "light_paraphrase",
                True,
                s,
                k,
                "plsh",
                "plla",
                "plra",
            )
        )
    # Weak paraphrases: Jaccard ~0.47-0.55, overlapping two-dir.
    for i, (s, k) in enumerate(
        (
            (18, 10),
            (20, 10),
            (22, 10),
            (22, 9),
            (16, 9),
            (19, 10),
            (21, 10),
            (17, 10),
            (23, 10),
            (20, 9),
        )
    ):
        rows.append(
            make_pair(
                f"para-weak-{i:02d}",
                "weak_paraphrase",
                True,
                s,
                k,
                "pwsh",
                "pwla",
                "pwra",
            )
        )
    for i, (s, k) in enumerate(((38, 2), (36, 2), (34, 3))):
        rows.append(
            make_pair(
                f"fork-{i:02d}",
                "one_parameter_fork",
                True,
                s,
                k,
                "fksh",
                "fkla",
                "fkra",
            )
        )
    # Same mechanism, rewritten vocabulary: low Jaccard, labelled should_collapse.
    # Catching these lexically requires a threshold that also collapses two-dir.
    for i, (s, k) in enumerate(((8, 18), (10, 20), (6, 16), (9, 19))):
        rows.append(
            make_pair(
                f"rewrite-{i:02d}",
                "full_rewrite",
                True,
                s,
                k,
                "rwsh",
                "rwla",
                "rwra",
            )
        )

    # DANGEROUS class: both records hold unique content. Must not collapse.
    # Jaccard planted in the same band as weak paraphrases.
    for i, (s, k) in enumerate(((20, 9), (18, 10), (22, 10), (24, 11), (16, 12), (22, 9))):
        p = make_pair(
            f"twodir-{i:02d}",
            "two_directional_divergence",
            False,
            s,
            k,
            "tdsh",
            "tdla",
            "tdra",
        )
        p["two_directional_divergence"] = True
        if not p["unique_left"] or not p["unique_right"]:
            raise RuntimeError(f"{p['pair_id']} is not two-directional")
        rows.append(p)

    # Genuinely distinct (low Jaccard, should not collapse).
    # Many low-Jaccard distinct pairs keep TNR high when two-dir pairs
    # false-collapse, which is what lures balanced accuracy downward.
    for i, (s, k) in enumerate(
        (
            (8, 20),
            (10, 18),
            (6, 22),
            (7, 19),
            (5, 21),
            (4, 22),
            (9, 20),
            (3, 24),
            (6, 20),
            (8, 18),
            (5, 23),
            (7, 21),
            (4, 19),
            (9, 22),
            (2, 25),
            (6, 18),
            (8, 23),
            (5, 20),
            (3, 21),
            (7, 24),
        )
    ):
        rows.append(
            make_pair(
                f"distinct-{i:02d}",
                "known_distinct",
                False,
                s,
                k,
                f"ds{i:02d}sh",
                f"ds{i:02d}la",
                f"ds{i:02d}ra",
            )
        )

    if not any(r["two_directional_divergence"] for r in rows):
        raise RuntimeError("labelled set missing two-directional-divergence")
    return rows


def score_live(row: dict[str, Any]) -> float:
    return round(jaccard(row["left_text"], row["right_text"]), 6)
