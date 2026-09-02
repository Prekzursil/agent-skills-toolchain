#!/usr/bin/env python3
"""Probe 1: known-good in-corpus idea is low novelty AND high quality.

A 2x2 of fixtures proves the axes are not 1-novelty: known-bad in corpus
is low novelty AND low quality; a genuinely new well-specified idea is
high novelty AND high quality; planted junk is high novelty AND low quality.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import novelty as N  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0053-probe1 {msg}")
    return 1


def main() -> int:
    corpus = N.load_corpus()
    cands = N.load_candidates()
    rows = {}
    for key in ("known_good", "known_bad_in_corpus", "planted_bad", "novel_good"):
        if key not in cands:
            return fail(f"missing candidate {key}")
        rows[key] = N.score_idea(cands[key], corpus)

    kg = rows["known_good"]
    kb = rows["known_bad_in_corpus"]
    junk = rows["planted_bad"]
    ng = rows["novel_good"]

    report = {
        "corpus_id": corpus["corpus_id"],
        "corpus_pin_sha256": corpus["pin_sha256"],
        "scores": {
            k: {
                "novelty": v["novelty"],
                "quality": v["quality"],
                "check": v["check"],
                "band": N.band(v),
                "match_kind": v["match_kind"],
                "match_id": v["match_id"],
            }
            for k, v in rows.items()
        },
        "separable": kg["quality"] != kg["novelty"],
    }
    print(json.dumps(report, sort_keys=True))

    if not (kg["low_novelty"] and kg["high_quality"]):
        return fail(
            f"known_good not low-N/high-Q novelty={kg['novelty']} quality={kg['quality']}"
        )
    if not (kb["low_novelty"] and kb["low_quality"]):
        return fail(
            f"known_bad_in_corpus not low-N/low-Q novelty={kb['novelty']} quality={kb['quality']}"
        )
    if not (junk["high_novelty"] and junk["low_quality"]):
        return fail(
            f"planted_bad not high-N/low-Q novelty={junk['novelty']} quality={junk['quality']}"
        )
    if not (ng["high_novelty"] and ng["high_quality"]):
        return fail(
            f"novel_good not high-N/high-Q novelty={ng['novelty']} quality={ng['quality']}"
        )
    if kg["quality"] == kg["novelty"]:
        return fail("known_good quality equals novelty; axes not shown separable")
    # If quality were 1-novelty, known-bad (low N) would be high Q.
    if kb["high_quality"]:
        return fail("known_bad_in_corpus scored high quality; quality collapsed to 1-novelty")
    print(
        "known_good low-N high-Q "
        f"N={kg['novelty']} Q={kg['quality']} "
        f"known_bad N={kb['novelty']} Q={kb['quality']} "
        f"junk N={junk['novelty']} Q={junk['quality']} "
        f"novel_good N={ng['novelty']} Q={ng['quality']}"
    )
    print("SUCCESS:CNL-0053-probe1 separable-axes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
