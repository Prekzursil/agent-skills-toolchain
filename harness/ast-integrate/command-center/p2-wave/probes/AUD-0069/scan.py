"""Pairwise body scan + planted-mutant calibration for AUD-0069."""
from __future__ import annotations

from typing import Iterable

import cards as C
import detectors as D
import mutants as M


def pair_score(a: dict, b: dict) -> dict:
    scored = D.score_pair(a["body"], b["body"])
    scored.update(
        {
            "left_id": a["id"],
            "right_id": b["id"],
            "left_title": a.get("title") or "",
            "right_title": b.get("title") or "",
            "left_source": a.get("source") or "",
            "right_source": b.get("source") or "",
        }
    )
    return scored


def pairwise(cards: list[dict]) -> list[dict]:
    out: list[dict] = []
    for i, left in enumerate(cards):
        for right in cards[i + 1 :]:
            if left["id"] == right["id"]:
                continue
            out.append(pair_score(left, right))
    return out


def _find(rows: Iterable[dict], left: str, right: str) -> dict:
    want = {left, right}
    for row in rows:
        if {row["left_id"], row["right_id"]} == want:
            return row
    raise KeyError(f"missing pair {left} {right}")


def calibration() -> dict:
    planted = M.scratch_cards()
    rows = pairwise(planted)
    rename = _find(rows, "AUD-0069-SEED", "AUD-0069-RENAME")
    para = _find(rows, "AUD-0069-SEED", "AUD-0069-PARA")
    fork = _find(rows, "AUD-0069-SEED", "AUD-0069-FORK")
    dist = _find(rows, "AUD-0069-SEED", "AUD-0069-DIST-A")
    both = _find(rows, "AUD-0069-DIST-A", "AUD-0069-DIST-B")
    rewrite = _find(rows, "AUD-0069-SEED", "AUD-0069-REWRITE")
    lexical_rename = bool(rename["lexical_fires"])
    embedding_rename = bool(rename["embedding_fires"])
    lexical_para = bool(para["lexical_fires"])
    embedding_para = bool(para["embedding_fires"])
    distinct_uncollapsed = (not dist["confirmed_same_mechanism"]) and (
        not both["confirmed_same_mechanism"]
    )
    fork_not_collapsed = not fork["confirmed_same_mechanism"]
    ok = (
        lexical_rename
        and embedding_rename
        and (not lexical_para)
        and embedding_para
        and distinct_uncollapsed
        and fork_not_collapsed
    )
    return {
        "ok": ok,
        "pairs": {
            "rename": rename,
            "paraphrase": para,
            "fork": fork,
            "seed_vs_distinct": dist,
            "distinct_vs_distinct": both,
            "full_rewrite": rewrite,
        },
        "lexical_catches_rename": lexical_rename,
        "embedding_catches_rename": embedding_rename,
        "lexical_catches_paraphrase": lexical_para,
        "embedding_catches_paraphrase": embedding_para,
        "fork_not_collapsed": fork_not_collapsed,
        "distinct_pair_not_collapsed": distinct_uncollapsed,
        "full_rewrite_class": rewrite["class"],
        "lexical_coverage": (
            "Token-Jaccard fires on exact-body renames and high-overlap "
            "one-parameter forks. A paraphrase of the same mechanism sits "
            f"at jaccard={para['jaccard']} (below {D.JAC_CANDIDATE}) so "
            "lexical-only coverage misses it. A full rewrite of the same "
            f"mechanism sits at jaccard={rewrite['jaccard']} / "
            f"embedding={rewrite['embedding_cosine']}, the same DISTINCT "
            "band as a genuinely different card. Stemmed-content cosine is "
            "the second detector; it is not a neural embedding and does not "
            "claim full-rewrite recall."
        ),
        "thresholds": {
            "jac_rename": D.JAC_RENAME,
            "jac_candidate": D.JAC_CANDIDATE,
            "emb_dup": D.EMB_DUP,
        },
        "planted_card_count": len(planted),
    }


def live_scan(live: dict | None = None) -> dict:
    payload = live if live is not None else C.load_live_cards()
    bodies = payload["cards"]
    rows = pairwise(bodies)
    confirmed = [r for r in rows if r["confirmed_same_mechanism"]]
    lexical = [r for r in rows if r["lexical_fires"]]
    embedding = [r for r in rows if r["embedding_fires"]]
    forks = [r for r in rows if r["class"] == "FORK-OR-NEAR"]
    paraphrases = [r for r in rows if r["class"] == "PARAPHRASE"]
    renames = [r for r in rows if r["class"] == "RENAME"]
    return {
        "contracted_cards": payload["contracted_cards"],
        "cards_found": payload["cards_found"],
        "cards_with_bodies": payload["cards_with_bodies"],
        "title_only": payload["title_only"],
        "corpus_present": payload["corpus_present"],
        "sources_used": payload["sources_used"],
        "candidate_paths": payload["candidate_paths"],
        "parse_errors": payload["parse_errors"],
        "source_kind": payload.get("source_kind") or "absent",
        "pairs_scored": len(rows),
        "lexical_candidates": len(lexical),
        "embedding_candidates": len(embedding),
        "confirmed_same_mechanism": len(confirmed),
        "rename_pairs": len(renames),
        "paraphrase_pairs": len(paraphrases),
        "fork_or_near_pairs": len(forks),
        "confirmed_pairs": confirmed[:50],
        "fork_pairs": forks[:50],
    }


def run() -> dict:
    live = C.load_live_cards()
    cal = calibration()
    scanned = live_scan(live)
    return {"calibration": cal, "live": scanned}
