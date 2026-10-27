#!/usr/bin/env python3
"""IMP-0367 probe2: evidence-decisive + no-retune controls (reviewer).

Both-states on the SAME fixture: under the production majority aggregator the
evidence-decisive curve is stable (N*=1, zero flips); under the N-modulated
aggregator the SAME votes move with N and the module honestly flags
protocol_is_n_sensitive instead of retuning. The tune_until_stable bad
practice is shown to collapse the n-sensitive flips that production publishes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.sensitivity import (  # noqa: E402
    curve,
    load_question,
    protocol_is_n_sensitive,
    tune_until_stable,
)

RECEIPT = REPO / "command-center/receipts/IMP-0367.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0367-probe2 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    nctl_ids = {n.get("id") for n in doc.get("negative_controls") or []}
    for want in ("IMP-0367-evidence-decisive-no-retune",
                 "IMP-0367-n-sensitive-curve-not-collapsed"):
        if want not in nctl_ids:
            return fail(f"receipt-negctl-missing:{want}")

    fx = HERE / "fixtures"
    ev = load_question(fx / "evidence-decisive.json")

    stable = curve(ev)
    if stable["flip_count"] != 0 or stable["stabilisation_point"] != 1:
        return fail(f"majority-not-stable:{stable['flip_count']},{stable['stabilisation_point']}")
    if protocol_is_n_sensitive(stable) is True:
        return fail("majority-falsely-flagged-n-sensitive")

    modulated = curve(ev, aggregator="AGG_N_MODULATED")
    if modulated["flip_count"] < 1:
        return fail("n-modulated-did-not-move")
    if protocol_is_n_sensitive(modulated) is not True:
        return fail("moved-curve-not-flagged")
    if modulated["published"] is not True:
        return fail("moved-curve-not-published")

    ns = load_question(fx / "n-sensitive.json")
    ns_curve = curve(ns)
    decisions = {r["decision"] for r in ns_curve["rows"]}
    if len(decisions) < 2:
        return fail("n-sensitive-curve-collapsed-in-production")
    collapsed = tune_until_stable(ns)
    if collapsed["flips_collapsed"] < 1 or collapsed["collapsed"] is not True:
        return fail("tune-until-stable-did-not-collapse")

    print(json.dumps({
        "probe": "probe2-evidence-decisive-control", "unit_id": "IMP-0367",
        "pass": True,
        "majority_stable": {"n_star": stable["stabilisation_point"],
                            "flips": stable["flip_count"]},
        "n_modulated": {"flips": modulated["flip_count"],
                        "flagged": protocol_is_n_sensitive(modulated)},
        "n_sensitive_published_flips": sorted(decisions),
        "tune_until_stable_collapse": collapsed,
    }, sort_keys=True))
    print("SUCCESS:IMP-0367-probe2 same votes, honest flag under moved aggregator; no retune")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
