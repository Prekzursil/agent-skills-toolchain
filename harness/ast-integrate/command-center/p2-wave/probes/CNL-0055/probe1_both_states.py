#!/usr/bin/env python3
"""Probe 1: padding vs saturated must be told apart, both directions recorded.

Also checks the design-note artifact recorded the same live classifications.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0055-saturation-versus-quota-filling-at-the-100-idea-target.md"
)


def _run(name: str) -> dict:
    pack = F.build(name)
    both = D.classify_both(pack["ledger"], pack["offered"], quota=pack["quota"])
    both["fixture"] = name
    both["expected_decision"] = pack["expected_decision"]
    return both


def main() -> int:
    padding = _run("padding")
    saturated = _run("saturated")
    p_dec = padding["decision"]
    s_dec = saturated["decision"]
    p_stop = padding["stop_round"]
    s_stop = saturated["stop_round"]
    p_y = padding["signal1_jaccard"]["unique_yield"]
    s_y = saturated["signal1_jaccard"]["unique_yield"]
    p_naive = padding["signal1_jaccard"]["naive_yield"]
    s_vol = saturated["signal2_raw_volume"]["offered_n"]

    print(f"padding_decision={p_dec} stop_round={p_stop} unique_yield={p_y} naive_yield={p_naive}")
    print(f"saturated_decision={s_dec} stop_round={s_stop} unique_yield={s_y} offered_n={s_vol}")
    print(f"padding_trigram_agrees={padding['methods_agree_on_decision']}")
    print(f"saturated_trigram_agrees={saturated['methods_agree_on_decision']}")

    if p_dec != "QUOTA_FILLING" or p_stop is not False or p_y != 0 or p_naive != 60:
        print("FAILED:CNL-0055-probe1 padding not classified as quota-filling")
        return 1
    if s_dec != "SATURATION" or s_stop is not True or s_y != 0 or s_vol != 3:
        print("FAILED:CNL-0055-probe1 saturated not classified as saturation")
        return 1
    if p_dec == s_dec:
        print("FAILED:CNL-0055-probe1 fixtures not told apart")
        return 1
    if not padding["methods_agree_on_decision"] or not saturated["methods_agree_on_decision"]:
        print("FAILED:CNL-0055-probe1 Jaccard and trigram decisions disagree")
        return 1
    if padding["satisfy_unique_quota"] is not False:
        print("FAILED:CNL-0055-probe1 padding must not satisfy unique quota")
        return 1
    if saturated["satisfy_unique_quota"] is not True:
        print("FAILED:CNL-0055-probe1 honest 100 unique should satisfy quota")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0055-probe1 design note missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0055-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0055" not in text:
        print("FAILED:CNL-0055-probe1 sentinel absent")
        return 1
    recorded = doc.get("both_states") or {}
    if recorded.get("padding_decision") != "QUOTA_FILLING":
        print("FAILED:CNL-0055-probe1 artifact padding_decision drift")
        return 1
    if recorded.get("saturated_decision") != "SATURATION":
        print("FAILED:CNL-0055-probe1 artifact saturated_decision drift")
        return 1
    if recorded.get("padding_unique_yield") != p_y or recorded.get("saturated_unique_yield") != s_y:
        print("FAILED:CNL-0055-probe1 artifact unique_yield drift")
        return 1
    if recorded.get("padding_naive_yield") != p_naive:
        print("FAILED:CNL-0055-probe1 artifact naive_yield drift")
        return 1
    which = doc.get("which_stops_the_round") or {}
    if which.get("stops") != "SATURATION" or which.get("does_not_stop") != "QUOTA_FILLING":
        print("FAILED:CNL-0055-probe1 which_stops_the_round drift")
        return 1
    if which.get("satisfy_quota_from_padding") is not False:
        print("FAILED:CNL-0055-probe1 padding must not satisfy quota")
        return 1
    print("SUCCESS:CNL-0055-probe1 padding-vs-saturated both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
