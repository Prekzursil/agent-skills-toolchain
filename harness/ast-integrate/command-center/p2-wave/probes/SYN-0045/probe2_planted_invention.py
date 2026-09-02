#!/usr/bin/env python3
"""Probe 2: planted invention must fail; every open decision has three parts.

Catalog tests:
  * planted invention: add an unsupported sentence -> the invariant must fail
  * every open decision carries recommendation, tradeoff, and default
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import claims as C  # noqa: E402

UNIT = "SYN-0045"
ART = REPO / "command-center" / "synthesis" / "SYN-0045.owner-brief.md"
PLANTED = (
    "The program obtained SOC 2 Type II certification in this wave "
    "and all residual unknowns are closed."
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    brief = C.payload(doc)
    source = brief.get("claim_source") or {}
    report_path = REPO / str(source.get("path") or "")
    if not report_path.is_file():
        return fail("bound report missing")
    report = C.load_json(report_path)

    clean = C.invariant(brief, report)
    if not clean["empty"]:
        return fail(f"live brief already dirty {clean['printed']}")

    planted = C.plant_invention(brief, PLANTED)
    dirty = C.invariant(planted, report)
    print(dirty["printed"])
    extras = [
        t
        for t in dirty["brief_minus_report"]
        if C.claim_key(PLANTED) == C.claim_key(t)
    ]
    if dirty["empty"]:
        return fail("planted invention was not detected")
    if not extras and not any(
        C.claim_key(PLANTED) == C.claim_key(t)
        for t in dirty["markdown_minus_report"]
    ):
        return fail(
            f"planted sentence missing from extras {dirty['brief_minus_report']}"
        )

    live = C.decisions_complete(brief.get("open_decisions") or [])
    if not live["ok"] or live["count"] < 1:
        return fail(f"live decisions incomplete {live}")

    sample = copy.deepcopy((brief.get("open_decisions") or [{}])[0])
    dropped = copy.deepcopy(sample)
    dropped["default_if_unanswered"] = "  "
    if "default_if_unanswered-empty" not in C.decision_errors(dropped):
        return fail("empty default accepted")
    dropped_rec = copy.deepcopy(sample)
    dropped_rec["recommendation"] = ""
    if "recommendation-empty" not in C.decision_errors(dropped_rec):
        return fail("empty recommendation accepted")
    dropped_to = copy.deepcopy(sample)
    dropped_to["strongest_tradeoff"] = ""
    if "strongest_tradeoff-empty" not in C.decision_errors(dropped_to):
        return fail("empty tradeoff accepted")

    print(
        json.dumps(
            {
                "probe": "probe2-planted-invention",
                "unit_id": UNIT,
                "planted_detected": True,
                "live_decisions_ok": True,
                "live_decision_count": live["count"],
                "empty_default_rejected": True,
                "empty_recommendation_rejected": True,
                "empty_tradeoff_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0045-probe2 planted invention fails; decisions complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
