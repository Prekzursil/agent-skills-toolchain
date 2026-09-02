#!/usr/bin/env python3
"""Probe 2: both-states control + negative control + independent reviewer.

FIRES on planted-bad (merely diverse / off-quota).
SILENT on known-good (hits the declared target).
Negative control: all-owner roster — the state the check is meant to reject.
Reviewer re-tabulates without reading the design note's argument.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import metric as M  # noqa: E402

NOTE = REPO / (
    "command-center/design/council/"
    "CNL-0017-stakeholder-balanced-selection-the-taxonomy-and-the-balanc.md"
)
FIX = HERE / "fixtures"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0017-probe2 {msg}")
    return 1


def recount_reverse(seats: list[dict]) -> dict[str, int]:
    """Independent tally: walk seats backwards, increment a dict."""
    counts = {c: 0 for c in M.CLASSES}
    for seat in reversed(seats):
        counts[str(seat["stakeholder_class"])] += 1
    return counts


def l1_half(observed: dict[str, int], target: dict[str, int]) -> int:
    """Re-derived I; not imported as a named slogan from the design note."""
    total = sum(
        abs(int(observed.get(c, 0)) - int(target.get(c, 0))) for c in M.CLASSES
    )
    extra = [k for k in observed if k not in M.CLASSES]
    total += sum(int(observed[k]) for k in extra)
    return total // 2


def main() -> int:
    thr = load(FIX / "threshold.json")
    i_star = int(thr["I_star"])
    target = load(FIX / "target.json")["target"]
    good = load(FIX / "roster-balanced.json")
    bad = load(FIX / "roster-unbalanced.json")
    neg = load(FIX / "roster-negative.json")
    even = load(FIX / "roster-even-off-target.json")

    g = M.score(good["seats"], target, i_star)
    b = M.score(bad["seats"], target, i_star)
    n = M.score(neg["seats"], target, i_star)

    print("BOTH_STATES_GOOD " + json.dumps(g, sort_keys=True))
    print("BOTH_STATES_BAD " + json.dumps(b, sort_keys=True))
    print("NEGATIVE_CONTROL " + json.dumps(n, sort_keys=True))

    if g["silent"] is not True or g["fires"] is not False:
        return fail("known-good was not SILENT")
    if b["fires"] is not True or b["silent"] is not False:
        return fail("planted-bad did not FIRE")
    if n["fires"] is not True:
        return fail("negative control (all-owner) did not FIRE")
    if n["D"] != 1 or n["I"] != 6:
        return fail(f"negative control unexpected I={n['I']} D={n['D']}")
    expected_unfilled = [
        c for c in M.CLASSES if c != "owner"
    ]
    if n["unfilled"] != expected_unfilled:
        return fail(f"unfilled {n['unfilled']}")

    # Verbatim record of what the check does on the state it is meant to reject.
    print(
        "NEGATIVE_CONTROL_VERBATIM "
        "roster-negative-all-owner: 8/8 seats labelled owner; "
        f"check FIRES because I={n['I']} > I_star={i_star}; "
        f"unfilled={n['unfilled']}; D={n['D']}. "
        "This is the occupancy the balance constraint exists to reject, "
        "not a diversity miss (richness is 1 because five target classes "
        "have zero seats)."
    )

    # Reviewer: reverse-walk recount, independent I, counterexample to D-as-balance.
    rg = recount_reverse(good["seats"])
    rb = recount_reverse(bad["seats"])
    rn = recount_reverse(neg["seats"])
    if rg != g["observed"] or rb != b["observed"] or rn != n["observed"]:
        return fail("reviewer recount disagrees with metric.census")
    if l1_half(rg, target) != g["I"] or l1_half(rb, target) != b["I"]:
        return fail("reviewer I disagrees")
    if l1_half(rn, target) != n["I"]:
        return fail("reviewer negative I disagrees")

    even_target = even["target_override"]
    e = M.score(even["seats"], even_target, i_star)
    print("REVIEWER_EVEN_OFF_TARGET " + json.dumps(e, sort_keys=True))
    if e["D"] != 6 or e["I"] != 1 or not e["fires"]:
        return fail("even-off-target did not refute evenness-as-balance")

    # Counterexample to "D == |C| implies balanced": the merely-diverse roster.
    if b["D"] != len(M.CLASSES) or b["I"] <= i_star:
        return fail("planted-bad is not a counterexample to richness-as-balance")

    if not NOTE.is_file():
        return fail("design note missing")
    note = json.loads(NOTE.read_text(encoding="utf-8"))
    rev = note.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer.independent is not true")
    inst = rev.get("counterexample_instance") or {}
    if inst.get("roster_id") != "roster-unbalanced-merely-diverse":
        return fail("reviewer counterexample instance missing")
    if str(rev.get("author_metric_refute") or "") == "REFUTED-NOT-ATTEMPTED":
        return fail("reviewer marked REFUTED-NOT-ATTEMPTED after attempting")

    print(
        json.dumps(
            {
                "probe": "probe2-both-states",
                "unit_id": "CNL-0017",
                "good_silent": True,
                "bad_fires": True,
                "negative_fires": True,
                "negative_I": n["I"],
                "negative_unfilled": n["unfilled"],
                "reviewer_recount_agrees": True,
                "richness_counterexample_I": b["I"],
                "even_off_target_I": e["I"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:CNL-0017-probe2 FIRES on planted-bad, SILENT on known-good, "
        "negative all-owner recorded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
