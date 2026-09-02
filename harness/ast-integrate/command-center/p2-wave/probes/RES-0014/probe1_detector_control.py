#!/usr/bin/env python3
"""Probe 1: detector control — seeded known-present issue is retrieved; absent state misses it."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from corpus import load_corpus  # noqa: E402
from search import SEEDED_TOKEN, classify, detector_control_both_states  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0014.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0014-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:RES-0014" not in text:
        print("FAILED:RES-0014-probe1 sentinel absent")
        return 1

    corpus = load_corpus()
    control = detector_control_both_states(corpus)
    classified = classify(corpus)

    if not control["pass"]:
        print("FAILED:RES-0014-probe1 both-states control", json.dumps(control))
        return 1
    if SEEDED_TOKEN not in "\n".join(r["blob"] for r in corpus):
        print("FAILED:RES-0014-probe1 seeded token missing from corpus")
        return 1
    if not classified["retrieval"]["seeded_retrieved"]:
        print("FAILED:RES-0014-probe1 seed not retrieved")
        return 1

    match_refs = {m["issue_ref"] for m in classified["matches"]}
    if "RES-0014-SEEDED-KNOWN-PRESENT" not in match_refs:
        print("FAILED:RES-0014-probe1 seed not in match table", sorted(match_refs))
        return 1
    if "RES-0014-DECOY-KEYWORD-ONLY" in match_refs:
        print("FAILED:RES-0014-probe1 decoy incorrectly matched")
        return 1

    decoy_non = [n for n in classified["non_matches"] if n.get("number") == 999001]
    if not decoy_non:
        print("FAILED:RES-0014-probe1 decoy not recorded as non-match")
        return 1

    art_control = doc.get("detector_control") or {}
    if not art_control.get("pass"):
        print("FAILED:RES-0014-probe1 artifact control not pass")
        return 1

    out = {
        "probe": "probe1-detector-control",
        "unit_id": "RES-0014",
        "pass": True,
        "seeded_token": SEEDED_TOKEN,
        "present_state_retrieves_seed": True,
        "absent_state_misses_seed": True,
        "decoy_not_matched": True,
        "match_count": len(classified["matches"]),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "seeded_retrieved=True absent_misses=True decoy_matched=False "
        f"matches={len(classified['matches'])}"
    )
    print("SUCCESS:RES-0014-probe1 detector control seeded-known-present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
