#!/usr/bin/env python3
"""Probe 1: lexical Jaccard over card bodies with planted-mutant calibration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan as S  # noqa: E402

OUT = HERE / "probe1-lexical.raw.json"


def main() -> int:
    result = S.run()
    cal = result["calibration"]
    live = result["live"]
    rename = cal["pairs"]["rename"]
    para = cal["pairs"]["paraphrase"]
    fork = cal["pairs"]["fork"]
    payload = {
        "probe": "probe1-lexical",
        "unit_id": "AUD-0069",
        "method": "unstemmed-token-set-jaccard",
        "calibration_ok": cal["ok"],
        "lexical_catches_rename": cal["lexical_catches_rename"],
        "lexical_catches_paraphrase": cal["lexical_catches_paraphrase"],
        "rename_jaccard": rename["jaccard"],
        "paraphrase_jaccard": para["jaccard"],
        "fork_jaccard": fork["jaccard"],
        "fork_class": fork["class"],
        "live_cards_with_bodies": live["cards_with_bodies"],
        "live_lexical_candidates": live["lexical_candidates"],
        "live_confirmed_same_mechanism": live["confirmed_same_mechanism"],
        "contracted_cards": live["contracted_cards"],
        "corpus_present": live["corpus_present"],
        "thresholds": cal["thresholds"],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not cal["lexical_catches_rename"]:
        print("FAILED:AUD-0069-probe1 lexical missed planted rename")
        return 1
    if cal["lexical_catches_paraphrase"]:
        print("FAILED:AUD-0069-probe1 lexical fired on paraphrase (not a distinct detector)")
        return 1
    if not cal["fork_not_collapsed"]:
        print("FAILED:AUD-0069-probe1 one-parameter fork collapsed as same mechanism")
        return 1
    if not cal["distinct_pair_not_collapsed"]:
        print("FAILED:AUD-0069-probe1 distinct pair collapsed")
        return 1
    print(
        "rename_jaccard="
        + str(rename["jaccard"])
        + " paraphrase_jaccard="
        + str(para["jaccard"])
        + " fork_jaccard="
        + str(fork["jaccard"])
        + " live_bodies="
        + str(live["cards_with_bodies"])
        + " live_lexical_candidates="
        + str(live["lexical_candidates"])
    )
    print("SUCCESS:AUD-0069-probe1 lexical near-duplicate planted-mutant calibration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
