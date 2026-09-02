#!/usr/bin/env python3
"""Probe 1: planted paraphrase must fire; planted distinct must stay silent.

A detector that flags both or neither is broken. Token-Jaccard used as if it
were the semantic detector flags neither on this plant, which is why the
unit requires embedding cosine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catalog as C  # noqa: E402
import planted as P  # noqa: E402
import scan as S  # noqa: E402


def main() -> int:
    entries = C.load_entries(REPO)
    live = S.run_scan(entries)
    if not live.get("ok"):
        print("FAILED:WFA-0136-probe1", live.get("reason"))
        print(json.dumps(live.get("calibration") or {}, indent=2)[:2000])
        return 1
    para = live["planted"]["paraphrase"]
    dist = live["planted"]["distinct"]
    if not para["semantic_flag"]:
        print("FAILED:WFA-0136-probe1 paraphrase not flagged by cosine")
        print(json.dumps(para, indent=2))
        return 1
    if dist["semantic_flag"]:
        print("FAILED:WFA-0136-probe1 distinct pair flagged by cosine")
        print(json.dumps(dist, indent=2))
        return 1
    if para["lexical_flag"]:
        print("FAILED:WFA-0136-probe1 paraphrase also Jaccard-flagged; plant too lexical")
        return 1
    if not live["jaccard_as_semantic_detector_broken"]:
        print("FAILED:WFA-0136-probe1 Jaccard-as-semantic was expected to flag neither")
        return 1
    if not live["detector_ok"]:
        print("FAILED:WFA-0136-probe1 detector_ok is false")
        return 1

    both_bad = para["semantic_flag"] and dist["semantic_flag"]
    neither = (not para["semantic_flag"]) and (not dist["semantic_flag"])
    if both_bad or neither:
        print("FAILED:WFA-0136-probe1 detector flags both or neither")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-planted-mutant-control",
                "unit_id": "WFA-0136",
                "anchor_id": P.ANCHOR_ID,
                "paraphrase_cosine": para["cosine"],
                "paraphrase_jaccard": para["jaccard"],
                "paraphrase_semantic_flag": True,
                "paraphrase_lexical_flag": False,
                "distinct_cosine": dist["cosine"],
                "distinct_jaccard": dist["jaccard"],
                "distinct_semantic_flag": False,
                "jaccard_as_semantic_detector": "BROKEN-flags-neither",
                "cosine_detector": "LIVE",
                "cosine_threshold": live["cosine_threshold"],
                "jaccard_threshold": live["jaccard_threshold"],
                "pass": True,
            },
            indent=2,
        )
    )
    print(
        f"paraphrase cos={para['cosine']:.4f} jac={para['jaccard']:.4f} "
        f"distinct cos={dist['cosine']:.4f} jac={dist['jaccard']:.4f}"
    )
    print(
        "SUCCESS:WFA-0136-probe1 planted paraphrase flagged, planted distinct silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
