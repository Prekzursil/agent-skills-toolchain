#!/usr/bin/env python3
"""Probe 1: planted-mutant control must pass before any real scan verdict."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lexical_scan as LS  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0007-lexical-duplicate-scan.json"
SENTINEL = "SUCCESS:WFA-0007"


def main() -> int:
    corpus = LS.load_corpus()
    planted = LS.planted_control(corpus["rows"], LS.THRESHOLD)
    print(json.dumps(planted, indent=2, sort_keys=True))
    bands = planted["planted"]["bands"]
    dup_scores = [b["score_vs_parent"] for b in bands if b["expect"] == "duplicate"]
    decoy_scores = [b["score_vs_parent"] for b in bands if b["expect"] == "decoy"]
    print(
        "planted dups scores="
        + ",".join(f"{s:.4f}" for s in dup_scores)
        + " decoys="
        + ",".join(f"{s:.4f}" for s in decoy_scores)
        + f" threshold={LS.THRESHOLD}"
    )
    if not planted["planted"]["pass"]:
        print("FAILED:WFA-0007-probe1 planted-mutant-control")
        return 1
    if not planted["negative_control"]["pass"]:
        print("FAILED:WFA-0007-probe1 negative-threshold")
        return 1
    nc = planted["negative_control"]
    if not (nc["fired_on_bad_state"] and nc["silent_on_good_state"]):
        print("FAILED:WFA-0007-probe1 both-states threshold mutant")
        return 1
    if not planted["collapse_union"]["pass"]:
        print("FAILED:WFA-0007-probe1 collapse-union")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        if SENTINEL not in text:
            print("FAILED:WFA-0007-probe1 sentinel absent from artifact")
            return 1
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print("FAILED:WFA-0007-probe1 artifact self-declared not delivering")
            return 1
        if "LEXICAL" not in str(doc.get("scope") or ""):
            print("FAILED:WFA-0007-probe1 lexical scope statement missing")
            return 1
    print("SUCCESS:WFA-0007-probe1 planted-mutant-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
