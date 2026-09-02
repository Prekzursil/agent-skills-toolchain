#!/usr/bin/env python3
"""Probe 2: different subjects must not be linked; both-states detector control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import edges as E  # noqa: E402

ART = REPO / "command-center/research/RES-0005.json"


def always_version_skew(_pair: dict) -> str:
    return "version_skew"


def always_other(_pair: dict) -> str:
    return "other"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0005-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    live_neg = E.classify_edge(C.NEGATIVE_CONTROL)
    live_ov = E.classify_edge(C.NEGATIVE_CONTROL_OVERLAP)
    print(f"neg1_edge={live_neg} neg2_edge={live_ov}")
    if live_neg is not None or live_ov is not None:
        print("FAILED:RES-0005-probe2 different subjects were linked")
        return 1

    broken_neg = always_version_skew(C.NEGATIVE_CONTROL)
    print(f"broken_always_version_skew_neg1={broken_neg}")
    if broken_neg is None:
        print("FAILED:RES-0005-probe2 broken classifier did not fire on NEG-01")
        return 1
    if broken_neg == live_neg:
        print("FAILED:RES-0005-probe2 live classifier matches always-version-skew (silent both states)")
        return 1

    gold = C.pair_by_id("GOLD-01")
    live_gold = E.classify_edge({k: v for k, v in gold.items() if k != "gold"})
    broken_gold = always_other(gold)
    print(f"live_gold={live_gold} always_other_gold={broken_gold}")
    if not E.gold_classifies_ok(live_gold):
        print("FAILED:RES-0005-probe2 GOLD-01 not version_skew")
        return 1
    if broken_gold == live_gold:
        print("FAILED:RES-0005-probe2 always-other matches live gold (silent both states)")
        return 1

    rec = doc.get("negative_control") or {}
    if rec.get("linked") is not False:
        print("FAILED:RES-0005-probe2 artifact negative_control.linked is not false")
        return 1
    if rec.get("edge_type") not in (None, "null"):
        print(f"FAILED:RES-0005-probe2 artifact recorded an edge for NEG-01: {rec.get('edge_type')}")
        return 1

    same = dict(C.NEGATIVE_CONTROL)
    same["a"] = dict(same["a"])
    same["b"] = dict(same["b"])
    same["a"]["subject"] = "plugin-json-unknown-fields"
    same["b"]["subject"] = "plugin-json-unknown-fields"
    same["subject"] = "plugin-json-unknown-fields"
    linked_when_same = E.classify_edge(same)
    print(f"mutant_same_subject_edge={linked_when_same}")
    if linked_when_same is None:
        print("FAILED:RES-0005-probe2 same-subject mutant produced no edge (detector silent)")
        return 1

    print(
        "SUCCESS:RES-0005-probe2 negative control different subjects unlinked; "
        "both-states detector control passed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
