#!/usr/bin/env python3
"""Probe 2: escalation fires on a known-bad stratum and stays silent on a good one.

Catalog test:
  Escalation fires: seed a stratum with known-bad verdicts above the threshold
  and confirm full-class re-verification is triggered.

Both-states, boundary, anti-thrash, and BLOCKED-denominator controls live here
so the trigger is not a one-sided story about the frozen ledger.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0323"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0323.json"

sys.path.insert(0, str(HERE))
import escalate as E  # noqa: E402
import prereg as P  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def row(cid: str, platform: str, gold: str, blocked: bool = False) -> dict:
    return {
        "blocked": blocked,
        "case_id": cid,
        "human_gold": gold,
        "oracle_type": "judged",
        "platform_verdict": platform,
    }


def main() -> int:
    prereg = P.load_prereg()
    threshold = float(prereg["error_rate_threshold"])
    if prereg.get("boundary") != "strict_gt":
        return fail("boundary is not strict_gt")

    # Known-bad class: population 12, sample 5 with 3 errors (0.6 > 0.10).
    pop_ids = [f"BAD-{i:02d}" for i in range(1, 13)]
    sample_bad = [
        row("BAD-01", "fail", "pass"),
        row("BAD-02", "fail", "pass"),
        row("BAD-03", "fail", "pass"),
        row("BAD-04", "fail", "fail"),
        row("BAD-05", "fail", "fail"),
    ]
    bad = E.decide(sample_bad, pop_ids, threshold, "judged:fail")
    print(
        f"known_bad fired={bad['fired']} rate={bad['rate']} "
        f"enqueued={len(bad['enqueued'])} class_size={bad['class_size']}"
    )
    if not bad["fired"]:
        return fail("known-bad stratum did not fire")
    if bad["enqueued"] != pop_ids:
        return fail("expansion did not enqueue the full class")
    if set(bad["enqueued"]) == {r["case_id"] for r in sample_bad}:
        return fail("expansion enqueued only the sample")
    if len(bad["enqueued"]) != 12:
        return fail("full-class size is not 12")

    # Clean class: 0/5 errors, population 12 → silent, empty enqueue.
    sample_good = [row(f"GOOD-{i:02d}", "pass", "pass") for i in range(1, 6)]
    good_ids = [f"GOOD-{i:02d}" for i in range(1, 13)]
    good = E.decide(sample_good, good_ids, threshold, "deterministic:pass")
    print(f"clean fired={good['fired']} rate={good['rate']} enqueued={good['enqueued']}")
    if good["fired"] or good["enqueued"]:
        return fail("clean stratum was not silent")

    # Boundary: exactly 1/10 = 0.10 must be silent under strict_gt.
    exact_sample = [row("EX-01", "fail", "pass")] + [
        row(f"EX-{i:02d}", "fail", "fail") for i in range(2, 11)
    ]
    exact_ids = [f"EX-{i:02d}" for i in range(1, 11)]
    exact = E.decide(exact_sample, exact_ids, threshold, "judged:fail")
    print(f"exact_threshold fired={exact['fired']} rate={exact['rate']}")
    if exact["rate"] != threshold:
        return fail(f"exact fixture rate {exact['rate']} is not the threshold")
    if exact["fired"]:
        return fail("rate == threshold must be silent under strict_gt")

    # Just above: 2/10 = 0.20 fires.
    above_sample = [
        row("AB-01", "fail", "pass"),
        row("AB-02", "fail", "pass"),
    ] + [row(f"AB-{i:02d}", "fail", "fail") for i in range(3, 11)]
    above_ids = [f"AB-{i:02d}" for i in range(1, 11)]
    above = E.decide(above_sample, above_ids, threshold, "judged:fail")
    print(f"just_above fired={above['fired']} rate={above['rate']}")
    if not above["fired"]:
        return fail("rate 0.20 did not fire")

    # Anti-thrash: a class already expanded must not be re-enqueued.
    again = E.decide(
        sample_bad,
        pop_ids,
        threshold,
        "judged:fail",
        already_expanded=set(pop_ids),
    )
    print(f"anti_thrash fired={again['fired']} enqueued={again['enqueued']}")
    if again["enqueued"]:
        return fail("already-expanded class was re-enqueued")
    if not again["fired"]:
        return fail("anti-thrash should still report fired=true with empty enqueue")

    # BLOCKED in the denominator must change the decision in at least one case:
    # 1 error + 9 blocked. With blocked in denom 1/10=0.10 silent; without, 1/1=1.0 fires.
    blocked_rows = [row("BL-01", "fail", "pass")] + [
        row(f"BL-{i:02d}", "fail", "fail", blocked=True) for i in range(2, 11)
    ]
    blocked_ids = [f"BL-{i:02d}" for i in range(1, 11)]
    excl = E.decide(blocked_rows, blocked_ids, threshold, "judged:fail")
    k_incl = 1
    n_incl = 10
    rate_incl = k_incl / n_incl
    print(
        f"blocked_excluded fired={excl['fired']} rate={excl['rate']} "
        f"n={excl['n']} rate_if_blocked_in_denom={rate_incl}"
    )
    if excl["n"] != 1 or excl["rate"] != 1.0:
        return fail("BLOCKED rows were not dropped from the denominator")
    if not excl["fired"]:
        return fail("excluding BLOCKED must fire this fixture")
    if rate_incl > threshold:
        return fail("control broken: including BLOCKED should be exactly threshold")
    # including BLOCKED would be silent (0.10 == threshold); excluding fires.
    if not (rate_incl == threshold and excl["fired"]):
        return fail("BLOCKED denominator did not change the decision")

    if not RECEIPT.is_file():
        return fail("receipt missing")
    rec = json.loads(RECEIPT.read_text(encoding="utf-8"))
    expansions = P.receipt_field(rec, "escalations") or []
    if not isinstance(expansions, list):
        return fail("receipt escalations missing")
    judged = next((e for e in expansions if e.get("stratum_id") == "judged:fail"), None)
    if judged is None or judged.get("fired") is not True:
        return fail("receipt did not record judged:fail expansion")
    if int(judged.get("class_size") or 0) != 20:
        return fail("receipt expansion class_size is not the judged:fail population")
    if len(judged.get("enqueued") or []) != 20:
        return fail("receipt expansion did not enqueue the full judged:fail class")

    print(
        json.dumps(
            {
                "anti_thrash_empty_enqueue": again["enqueued"] == [],
                "blocked_changes_decision": True,
                "clean_silent": good["fired"] is False,
                "exact_threshold_silent": exact["fired"] is False,
                "known_bad_full_class": len(bad["enqueued"]) == 12,
                "pass": True,
                "probe": "probe2-escalation",
                "unit_id": UNIT,
            },
            sort_keys=True,
        )
    )
    print(f"SUCCESS:{UNIT}-probe2 escalation fires and stays silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
