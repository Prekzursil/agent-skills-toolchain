#!/usr/bin/env python3
"""IMP-0367 probe1: publish the decision-versus-N curve per question.

Live re-run of E1 + E2: for each fixture question the full curve is published
with its stabilisation point, and the configured default is compared against
N* (including the honest defect on Q-default-below, whose default N=3 sits
below N*=5 and would emit the wrong answer).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.sensitivity import compare_default, curve, load_question, public_row  # noqa: E402

RECEIPT = REPO / "command-center/receipts/IMP-0367.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0367-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    fx = HERE / "fixtures"
    results = {}
    for name in ("evidence-decisive", "n-sensitive", "default-below"):
        q = load_question(fx / f"{name}.json")
        c = curve(q)
        cd = compare_default(q)
        row = public_row(c)
        if c["published"] is not True or not c["rows"]:
            return fail(f"{name}:curve-not-published")
        results[name] = {"curve": row, "default": cd}

    ev = results["evidence-decisive"]
    if ev["curve"]["n_star"] != 1 or ev["curve"]["flip_count"] != 0:
        return fail(f"evidence-decisive-curve:{ev['curve']}")
    if ev["default"]["default_above_stable"] is not True:
        return fail("default-not-above-N*")

    ns = results["n-sensitive"]
    if ns["curve"]["n_star"] != 7:
        return fail(f"n-sensitive-N*:{ns['curve']['n_star']}")
    if ns["curve"]["flip_count"] < 1 or ns["curve"]["is_n_sensitive"] is not True:
        return fail("n-sensitive-not-flagged")
    if ns["default"]["decision_at_default"] == ns["default"]["stable_decision"]:
        return fail("n-sensitive-default-hides-sensitivity")

    db = results["default-below"]
    if db["default"]["stabilisation_point"] != 5:
        return fail("default-below-N*")
    if db["default"]["decision_at_default"] != "ACCEPT":
        return fail("default-below-decision-at-3")
    if db["default"]["stable_decision"] != "REJECT":
        return fail("default-below-stable")
    if db["default"]["default_above_stable"] is not False:
        return fail("default-below-not-surfaced-honestly")

    print(json.dumps({
        "probe": "probe1-decision-vs-n", "unit_id": "IMP-0367", "pass": True,
        "questions": {k: {
            "n_star": v["curve"]["n_star"],
            "stable": v["curve"]["stable_decision"],
            "flips": v["curve"]["flip_count"],
            "default_n": v["default"]["default_n"],
            "decision_at_default": v["default"]["decision_at_default"],
            "default_above_stable": v["default"]["default_above_stable"],
        } for k, v in results.items()},
    }, sort_keys=True))
    print("SUCCESS:IMP-0367-probe1 curves published; defaults compared against N*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
