#!/usr/bin/env python3
"""Probe 1: Recall@5 lexical vs semantic on the IMP-0388 planted-mutant set.

Same control set, same seed. Verbatim queries must hit BOTH methods (two-sided
control). Paraphrase queries must miss lexical and hit semantic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.lexical import jaccard_int, tokenize  # noqa: E402
from router.semantic_matcher import (  # noqa: E402
    load_planted,
    measure_recall,
    pair_scores,
    pin_identity,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0390-probe1 {msg}")
    return 1


def main() -> int:
    planted = load_planted()
    caps = planted["capabilities"]
    seed = int(planted["seed"])
    k = int(planted["k"])
    ident = pin_identity()
    if not ident.get("digest_matches_pin"):
        return fail(f"model digest does not match pin: {ident}")

    verbatim = measure_recall(planted["verbatim_queries"], caps, k=k, seed=seed)
    paraphrase = measure_recall(planted["paraphrase_queries"], caps, k=k, seed=seed)

    pair = planted["imp0388_planted_pair"]
    by_id = {c["capability_id"]: c for c in caps}
    left = by_id[pair["left_id"]]["description"]
    right = by_id[pair["right_id"]]["description"]
    pair_m = pair_scores(left, right, seed=seed)
    pair_lex = jaccard_int(tokenize(left), tokenize(right))

    ok = (
        verbatim["lexical_recall_at_k"] == 1.0
        and verbatim["semantic_recall_at_k"] == 1.0
        and paraphrase["lexical_recall_at_k"] == 0.0
        and paraphrase["semantic_recall_at_k"] == 1.0
        and pair_lex == 0
        and int(pair_m["semantic_cosine_e9"]) > 0
        and ident["model_id"] == "imp0390-local-concept-embed-v1.0.0"
    )
    payload = {
        "probe": "probe1-recall-at-5",
        "unit_id": "IMP-0390",
        "pass": ok,
        "k": k,
        "seed": seed,
        "pinned_model_id": ident["model_id"],
        "pinned_model_digest": ident["pinned_sha256"],
        "live_model_digest": ident["live_sha256"],
        "verbatim": {
            "n": verbatim["n"],
            "lexical_recall_at_5": verbatim["lexical_recall_at_k"],
            "semantic_recall_at_5": verbatim["semantic_recall_at_k"],
            "lexical_hits": verbatim["lexical_hits"],
            "semantic_hits": verbatim["semantic_hits"],
        },
        "paraphrase": {
            "n": paraphrase["n"],
            "lexical_recall_at_5": paraphrase["lexical_recall_at_k"],
            "semantic_recall_at_5": paraphrase["semantic_recall_at_k"],
            "lexical_hits": paraphrase["lexical_hits"],
            "semantic_hits": paraphrase["semantic_hits"],
            "rows": paraphrase["rows"],
        },
        "imp0388_planted_pair": {
            "left_id": pair["left_id"],
            "right_id": pair["right_id"],
            "lexical_jaccard_e9": pair_lex,
            "semantic_cosine_e9": pair_m["semantic_cosine_e9"],
            "lexical_cannot_see_pair": pair_lex == 0,
            "semantic_recovers_pair": int(pair_m["semantic_cosine_e9"]) > 0,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        return fail("recall contract not met")
    print(
        "SUCCESS:IMP-0390-probe1 paraphrase lexical R@5="
        f"{paraphrase['lexical_recall_at_k']} semantic R@5="
        f"{paraphrase['semantic_recall_at_k']} model={ident['model_id']} "
        f"digest={ident['pinned_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
