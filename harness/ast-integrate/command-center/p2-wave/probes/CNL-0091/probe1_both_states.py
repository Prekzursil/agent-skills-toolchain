#!/usr/bin/env python3
"""Probe 1: detector-control first, then both-states, then genuine-agreement.

Known-present (collapsed-calibrate) is scored before any absence claim.
Stance Jaccard is recorded as a foil: it is low on BOTH collapse and
genuine agreement, so it cannot be the fire statistic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"
ORDER = [
    "collapsed-calibrate",
    "diverse-calibrate",
    "genuine-agreement",
    "collapsed-paraphrase",
]


def by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def main() -> int:
    scored = D.score_all()
    idx = by_id(scored)
    missing = [i for i in ORDER if i not in idx]
    if missing:
        print("FAILED:CNL-0091-probe1 missing fixtures", missing)
        return 1

    verbatim = []
    # Detector-control: known-present MUST be evaluated first.
    first = ORDER[0]
    if first != "collapsed-calibrate":
        print("FAILED:CNL-0091-probe1 control order mutated")
        return 1
    plant = idx[first]
    line = (
        f"CONTROL-FIRST id={plant['id']} d_combined={plant['d_combined']} "
        f"d_stance={plant['d_stance']} fired={plant['fired']} gate={plant['gate']}"
    )
    verbatim.append(line)
    print(line)
    if not plant["fired"]:
        print(
            "FAILED:CNL-0091-probe1 fixture-broken: known-present did not fire "
            "(not a mechanism attempt; fix the planted-bad fixture)"
        )
        return 1

    good = idx["diverse-calibrate"]
    line = (
        f"KNOWN-GOOD id={good['id']} d_combined={good['d_combined']} "
        f"d_stance={good['d_stance']} fired={good['fired']}"
    )
    verbatim.append(line)
    print(line)
    if good["fired"]:
        print("FAILED:CNL-0091-probe1 false-positive on diverse-calibrate")
        return 1

    agree = idx["genuine-agreement"]
    line = (
        f"NEG-CONTROL id={agree['id']} d_combined={agree['d_combined']} "
        f"d_stance={agree['d_stance']} fired={agree['fired']}"
    )
    verbatim.append(line)
    print(line)
    if agree["fired"]:
        print("FAILED:CNL-0091-probe1 genuine-agreement was treated as collapse")
        return 1

    para = idx["collapsed-paraphrase"]
    line = (
        f"HOLD OUT id={para['id']} d_combined={para['d_combined']} "
        f"d_stance={para['d_stance']} fired={para['fired']}"
    )
    verbatim.append(line)
    print(line)
    if not para["fired"]:
        print("FAILED:CNL-0091-probe1 paraphrase-collapse did not fire")
        return 1

    if agree["d_stance"] >= 0.15:
        print("FAILED:CNL-0091-probe1 agreement stance foil not low")
        return 1
    if plant["d_stance"] >= 0.15:
        print("FAILED:CNL-0091-probe1 collapsed stance foil not low")
        return 1
    if not (plant["d_combined"] < D.COLLAPSE_GATE <= agree["d_combined"]):
        print("FAILED:CNL-0091-probe1 gate does not separate collapse from agreement")
        return 1
    if abs(agree["d_stance"] - plant["d_stance"]) > 0.15 and agree["d_combined"] < 0.5:
        print("FAILED:CNL-0091-probe1 unexpected stance/role coupling")
        return 1

    doc = {
        "unit_id": "CNL-0091",
        "known_present_evaluated_first": True,
        "fired_on_bad": True,
        "silent_on_good": True,
        "silent_on_genuine_agreement": True,
        "gate": D.COLLAPSE_GATE,
        "collapsed_calibrate": plant,
        "diverse_calibrate": good,
        "genuine_agreement": agree,
        "collapsed_paraphrase": para,
        "verbatim": verbatim,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_bad=True silent_on_good=True silent_on_agree=True "
        f"d_collapse={plant['d_combined']} d_agree={agree['d_combined']} "
        f"d_stance_collapse={plant['d_stance']} d_stance_agree={agree['d_stance']}"
    )
    print("SUCCESS:CNL-0091-probe1 both-states control-first")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
