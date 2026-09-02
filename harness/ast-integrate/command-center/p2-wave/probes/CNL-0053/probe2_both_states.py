#!/usr/bin/env python3
"""Probe 2: both-states control + independent reviewer counterexamples.

The check (junk_novelty_check) FIRES on planted-bad high-N/low-Q junk and
is SILENT on the known-good in-corpus restatement.

Reviewer path does not reuse the author's mechanism-id collapse. It uses
character 3-gram Jaccard on compact text (a different measurement) and
must still call the unlabeled checksum paraphrase close to the corpus
while refusing to collapse 'checksum as cache key' into PA-001.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import novelty as N  # noqa: E402

ALNUM = re.compile(r"[^a-z0-9]+")


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0053-probe2 {msg}")
    return 1


def compact(text: str) -> str:
    return ALNUM.sub("", (text or "").lower())


def trigrams(text: str) -> frozenset[str]:
    s = compact(text)
    if len(s) < 3:
        return frozenset({s} if s else set())
    return frozenset(s[i : i + 3] for i in range(len(s) - 2))


def trigram_jaccard(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def reviewer_novelty(idea: dict, corpus: dict) -> dict:
    """Independent of mechanism-id equality and of word Jaccard."""
    text = str(idea.get("text") or "")
    best = 0.0
    best_id = None
    best_text = ""
    for row in corpus.get("items") or []:
        sim = trigram_jaccard(text, str(row.get("text") or ""))
        if sim > best:
            best = sim
            best_id = str(row.get("id") or "")
            best_text = str(row.get("text") or "")
    return {
        "novelty": round(1.0 - best, 6),
        "trigram_jaccard": round(best, 6),
        "match_id": best_id,
        "match_text": best_text,
        "method": "char-3gram-jaccard",
    }


def main() -> int:
    corpus = N.load_corpus()
    cands = N.load_candidates()
    good = N.score_idea(cands["known_good"], corpus)
    bad = N.score_idea(cands["planted_bad"], corpus)
    para = N.score_idea(cands["paraphrase_unlabeled"], corpus)
    dist = N.score_idea(cands["reviewer_related_but_distinct"], corpus)

    good_check = good["check"]
    bad_check = bad["check"]
    print(
        json.dumps(
            {
                "both_states": {
                    "known_good_check": good_check,
                    "planted_bad_check": bad_check,
                    "known_good_novelty": good["novelty"],
                    "known_good_quality": good["quality"],
                    "planted_bad_novelty": bad["novelty"],
                    "planted_bad_quality": bad["quality"],
                },
                "negative_control": {
                    "state_meant_to_reject": "planted_bad high-novelty low-quality junk that a novelty-only gate would accept",
                    "check_on_that_state": bad_check,
                    "check_on_known_good": good_check,
                },
            },
            sort_keys=True,
        )
    )

    if bad_check != "FIRE":
        return fail(f"check SILENT on planted-bad (got {bad_check})")
    if good_check != "SILENT":
        return fail(f"check FIRED on known-good (got {good_check})")
    print(
        "BOTH-STATES known_good=SILENT planted_bad=FIRE "
        f"good(N={good['novelty']},Q={good['quality']}) "
        f"bad(N={bad['novelty']},Q={bad['quality']})"
    )
    print(
        "NEGATIVE-CONTROL verbatim: on the planted-bad high-novelty "
        f"low-quality fixture the check returns {bad_check}; on the "
        f"known-good in-corpus restatement it returns {good_check}."
    )

    # Author backstop: unlabeled paraphrase must still be low novelty via surface Jaccard.
    if not para["low_novelty"]:
        return fail(
            f"unlabeled paraphrase not low novelty via surface Jaccard N={para['novelty']} "
            f"jaccard={para['surface_jaccard']}"
        )
    if para["match_kind"] != "surface-jaccard":
        return fail(f"unlabeled paraphrase used {para['match_kind']}, expected surface-jaccard")

    # Reviewer: different mechanism (char 3-grams), never saw author match_kind.
    rev_para = reviewer_novelty(cands["paraphrase_unlabeled"], corpus)
    rev_junk = reviewer_novelty(cands["planted_bad"], corpus)
    rev_dist = reviewer_novelty(cands["reviewer_related_but_distinct"], corpus)
    rev_good = reviewer_novelty(cands["known_good"], corpus)
    print(
        json.dumps(
            {
                "reviewer": {
                    "method": "char-3gram-jaccard",
                    "paraphrase_unlabeled": rev_para,
                    "planted_bad": rev_junk,
                    "related_but_distinct": rev_dist,
                    "known_good": rev_good,
                    "author_unlabeled_paraphrase": {
                        "novelty": para["novelty"],
                        "surface_jaccard": para["surface_jaccard"],
                        "match_id": para["match_id"],
                    },
                    "author_related_but_distinct": {
                        "novelty": dist["novelty"],
                        "match_kind": dist["match_kind"],
                        "match_id": dist["match_id"],
                        "quality": dist["quality"],
                    },
                }
            },
            sort_keys=True,
        )
    )

    if rev_para["novelty"] > N.LOW_NOVELTY_MAX:
        return fail(
            f"reviewer 3-gram called unlabeled paraphrase novel N={rev_para['novelty']}"
        )
    if rev_good["novelty"] > N.LOW_NOVELTY_MAX:
        return fail(f"reviewer 3-gram called known-good novel N={rev_good['novelty']}")
    if rev_junk["novelty"] < N.HIGH_NOVELTY_MIN:
        return fail(f"reviewer 3-gram failed to call junk novel N={rev_junk['novelty']}")
    # Counterexample instance against naive 'contains checksum' collapse:
    # cache-key idea must remain high novelty vs corpus (not PA-001).
    if dist["match_kind"] == "mechanism-id" and dist["match_id"] == "PA-001":
        return fail("author collapsed cache-key checksum into PA-001 via mechanism-id")
    if not dist["high_novelty"]:
        return fail(
            f"related-but-distinct cache-key idea not high novelty N={dist['novelty']} "
            f"match={dist['match_id']}"
        )
    if rev_dist["match_id"] == "PA-001" and rev_dist["novelty"] <= N.LOW_NOVELTY_MAX:
        return fail("reviewer 3-gram collapsed cache-key idea into PA-001")
    if not dist["high_quality"]:
        return fail("cache-key idea lost quality; reviewer counterexample unusable")

    print(
        "REVIEWER counterexample instance C-CHECKSUM-CACHE-KEY: "
        "shares the word checksum with PA-001 but is a different mechanism; "
        f"author N={dist['novelty']} match_kind={dist['match_kind']} "
        f"reviewer_3gram N={rev_dist['novelty']} match={rev_dist['match_id']}. "
        "Paraphrase without mechanism id remains low-N on both author Jaccard "
        f"(N={para['novelty']}) and reviewer 3-gram (N={rev_para['novelty']}). "
        "No refutation of separable axes. Verdict PASS."
    )
    print("SUCCESS:CNL-0053-probe2 both-states reviewer-counterexample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
