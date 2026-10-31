#!/usr/bin/env python3
"""Probe 2: embedding-cosine rescan of the SAME planted mutants as probe 1."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

OUT = HERE / "probe2-embedding.raw.json"


def main() -> int:
    result = S.run()
    cal = result["calibration"]
    live = result["live"]
    rename = cal["pairs"]["rename"]
    para = cal["pairs"]["paraphrase"]
    fork = cal["pairs"]["fork"]
    rewrite = cal["pairs"]["full_rewrite"]
    payload = {
        "probe": "probe2-embedding",
        "unit_id": "AUD-0069",
        "method": "stemmed-content-word-tf-cosine",
        "calibration_ok": cal["ok"],
        "embedding_catches_rename": cal["embedding_catches_rename"],
        "embedding_catches_paraphrase": cal["embedding_catches_paraphrase"],
        "lexical_catches_paraphrase": cal["lexical_catches_paraphrase"],
        "rename_embedding_cosine": rename["embedding_cosine"],
        "paraphrase_embedding_cosine": para["embedding_cosine"],
        "fork_embedding_cosine": fork["embedding_cosine"],
        "fork_class": fork["class"],
        "full_rewrite_class": rewrite["class"],
        "full_rewrite_embedding_cosine": rewrite["embedding_cosine"],
        "live_cards_with_bodies": live["cards_with_bodies"],
        "live_embedding_candidates": live["embedding_candidates"],
        "live_paraphrase_pairs": live["paraphrase_pairs"],
        "live_confirmed_same_mechanism": live["confirmed_same_mechanism"],
        "contracted_cards": live["contracted_cards"],
        "corpus_present": live["corpus_present"],
        "lexical_coverage": cal["lexical_coverage"],
        "thresholds": cal["thresholds"],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not cal["embedding_catches_rename"]:
        print("FAILED:AUD-0069-probe2 embedding missed planted rename")
        return 1
    if not cal["embedding_catches_paraphrase"]:
        print("FAILED:AUD-0069-probe2 embedding missed planted paraphrase")
        return 1
    if cal["lexical_catches_paraphrase"]:
        print("FAILED:AUD-0069-probe2 paraphrase was already a lexical hit; detectors are not distinct")
        return 1
    if not cal["fork_not_collapsed"]:
        print("FAILED:AUD-0069-probe2 one-parameter fork collapsed as same mechanism")
        return 1
    if not cal["distinct_pair_not_collapsed"]:
        print("FAILED:AUD-0069-probe2 distinct pair collapsed")
        return 1
    print(
        "rename_cos="
        + str(rename["embedding_cosine"])
        + " paraphrase_cos="
        + str(para["embedding_cosine"])
        + " fork_cos="
        + str(fork["embedding_cosine"])
        + " rewrite_cos="
        + str(rewrite["embedding_cosine"])
        + " live_bodies="
        + str(live["cards_with_bodies"])
        + " live_confirmed="
        + str(live["confirmed_same_mechanism"])
    )
    print("SUCCESS:AUD-0069-probe2 embedding-cosine planted-mutant rescan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
