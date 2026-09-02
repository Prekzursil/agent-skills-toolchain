#!/usr/bin/env python3
"""Probe 2: demotion rule — single-confirmer CONFIRMED at sub-threshold kappa
becomes PARTIAL; dual independent agreement does not demote.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import demotion as D  # noqa: E402
import kappa as K  # noqa: E402

UNIT = "CNF-0134"
RECEIPT = REPO / "command-center" / "receipts" / "CNF-0134.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    prereg = K.load_prereg()
    threshold = float(prereg["kappa_threshold"])

    single = {
        "claim_id": "CNF-0134-PROBE-SINGLE",
        "confirmer_count": 1,
        "confirmers": [{"vendor": "anthropic", "verdict": "CONFIRMED"}],
        "verdict": "CONFIRMED",
    }
    low = D.apply_demotion(single, kappa=0.12, threshold=threshold)
    print(
        f"single_subthreshold verdict={low['verdict']} "
        f"applied={low['demotion_applied']} reason={low['demotion_reason']}"
    )
    if low["verdict"] != "PARTIAL" or low.get("prior_verdict") != "CONFIRMED":
        return fail("single-confirmer CONFIRMED was not demoted to PARTIAL")
    if low["demotion_applied"] is not True:
        return fail("demotion_applied is not true")
    if low["demotion_reason"] != "sub-threshold-kappa-single-confirmer":
        return fail("unexpected demotion_reason")

    dual = {
        "claim_id": "CNF-0134-PROBE-DUAL",
        "confirmer_count": 2,
        "confirmers": [
            {"vendor": "anthropic", "verdict": "CONFIRMED"},
            {"vendor": "openai", "verdict": "CONFIRMED"},
        ],
        "verdict": "CONFIRMED",
    }
    dual_out = D.apply_demotion(dual, kappa=0.12, threshold=threshold)
    print(
        f"dual_agree_subthreshold verdict={dual_out['verdict']} "
        f"applied={dual_out['demotion_applied']} "
        f"reason={dual_out['demotion_reason']}"
    )
    if dual_out["verdict"] != "CONFIRMED":
        return fail("dual independent agree was demoted")
    if dual_out["demotion_applied"] is not False:
        return fail("dual agree must not set demotion_applied")
    if dual_out["demotion_reason"] != "independent-confirmers-agree":
        return fail("dual agree reason mismatch")

    high = D.apply_demotion(single, kappa=0.81, threshold=threshold)
    print(
        f"single_above_threshold verdict={high['verdict']} "
        f"applied={high['demotion_applied']}"
    )
    if high["verdict"] != "CONFIRMED" or high["demotion_applied"] is not False:
        return fail("demotion fired above threshold")

    same_vendor = {
        "claim_id": "CNF-0134-PROBE-SAME-VENDOR",
        "confirmers": [
            {"vendor": "anthropic", "verdict": "CONFIRMED"},
            {"vendor": "anthropic", "verdict": "CONFIRMED"},
        ],
        "verdict": "CONFIRMED",
    }
    sv = D.apply_demotion(same_vendor, kappa=0.12, threshold=threshold)
    print(
        f"same_vendor_pair confirmer_count={D.confirmer_count(same_vendor)} "
        f"applied={sv['demotion_applied']} verdict={sv['verdict']}"
    )
    # Two rows from one vendor are not independent; count==2 so the
    # single-confirmer clause does not fire either. Record stays CONFIRMED
    # with demotion_applied false (this unit only demotes n==1).
    if sv["verdict"] != "CONFIRMED" or sv["demotion_applied"] is not False:
        return fail("same-vendor pair mishandled")

    if RECEIPT.is_file():
        rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
        view = K.domain_view(rec)
        rule = view.get("demotion_rule") or {}
        if str(rule.get("single_confirmer_confirmed_becomes")) != "PARTIAL":
            return fail("receipt demotion_rule missing PARTIAL target")
        measured = float(view["point_estimate"])
        active = bool(rule.get("active_on_this_frame"))
        expected_active = measured < threshold
        if active != expected_active:
            return fail(
                f"active_on_this_frame={active} but kappa={measured} "
                f"threshold={threshold}"
            )

    print(
        json.dumps(
            {
                "dual_not_demoted": True,
                "pass": True,
                "probe": "probe2-demotion",
                "single_demoted_to": low["verdict"],
                "unit_id": UNIT,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe2 demotion fires on single, not on dual-agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
