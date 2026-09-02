#!/usr/bin/env python3
"""Probe 2: quorum-sensitivity both-states (mechanically different from probe 1).

Probe 1 scores labelled reasoning/ballot pairs. This probe never reads those
labels. It builds two sibling 5-seat profiles that differ by one filler ballot
and checks:

  planted  — 2 aye, 2 nay, 1 abstain with implied AYE → abstention is pivotal
             and flagged strategic_abstention
  control  — 3 aye, 1 nay, 1 abstain with the SAME implied AYE → not pivotal,
             strategic_abstention silent

A third sibling uses STANCE:ABSTAIN in the planted numbers: pivotal but not
strategic (principled vs strategic discriminator).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.antifail.strategic import (  # noqa: E402
    evaluate_profile,
    quorum_sensitivity,
    tally,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0347-probe2 {msg}")
    return 1


def seat(pid: str, ballot: str, text: str) -> dict:
    return {
        "participant_id": pid,
        "ballot": ballot,
        "ballot_t": 10,
        "reasoning_history": [{"t": 1, "text": text}],
    }


def profile(pid: str, n_aye: int, n_nay: int, target_text: str) -> dict:
    seats = []
    for i in range(n_aye):
        seats.append(seat(f"{pid}-aye-{i}", "aye", f"Filler aye {i}. STANCE:AYE"))
    for i in range(n_nay):
        seats.append(seat(f"{pid}-nay-{i}", "nay", f"Filler nay {i}. STANCE:NAY"))
    seats.append(seat("TARGET", "abstain", target_text))
    return {
        "profile_id": pid,
        "quorum": 3,
        "threshold": "majority_of_seated",
        "abstention_policy": "include_in_denominator",
        "n_seats": 5,
        "seats": seats,
    }


def main() -> int:
    planted = profile("planted", 2, 2, "I favour the motion. STANCE:AYE")
    control = profile("control", 3, 1, "I favour the motion. STANCE:AYE")
    principled = profile(
        "principled",
        2,
        2,
        "Out of domain; I will not invent a position. STANCE:ABSTAIN",
    )

    # Signal 1: quorum_sensitivity uses only ballots + policy, not reasoning.
    s_planted = quorum_sensitivity(planted)
    s_control = quorum_sensitivity(control)
    s_prin = quorum_sensitivity(principled)

    # Signal 2: evaluate_profile adds the reasoning conjunction.
    e_planted = evaluate_profile(planted)
    e_control = evaluate_profile(control)
    e_prin = evaluate_profile(principled)

    def target(ev: dict) -> dict:
        return next(d for d in ev["detections"] if d["participant_id"] == "TARGET")

    t_p, t_c, t_r = target(e_planted), target(e_control), target(e_prin)

    report = {
        "probe": "probe2-quorum-sensitivity",
        "unit_id": "IMP-0347",
        "policy_id": s_planted["policy_id"],
        "planted": {
            "actual": s_planted["actual"]["outcome"],
            "pivotal_ids": s_planted["pivotal_ids"],
            "target": {
                "pivotal": t_p["pivotal_abstention"],
                "strategic_abstention": t_p["strategic_abstention"],
                "implied": t_p["implied_stance"],
                "honest": t_p.get("honest_counterfactual"),
            },
        },
        "control": {
            "actual": s_control["actual"]["outcome"],
            "pivotal_ids": s_control["pivotal_ids"],
            "target": {
                "pivotal": t_c["pivotal_abstention"],
                "strategic_abstention": t_c["strategic_abstention"],
                "implied": t_c["implied_stance"],
                "honest": t_c.get("honest_counterfactual"),
            },
        },
        "principled": {
            "actual": s_prin["actual"]["outcome"],
            "pivotal_ids": s_prin["pivotal_ids"],
            "target": {
                "pivotal": t_r["pivotal_abstention"],
                "strategic_abstention": t_r["strategic_abstention"],
                "implied": t_r["implied_stance"],
                "honest": t_r.get("honest_counterfactual"),
            },
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if s_planted["actual"]["outcome"] != "FAIL":
        return fail(f"planted actual {s_planted['actual']}")
    if "TARGET" not in s_planted["pivotal_ids"]:
        return fail(f"planted not pivotal {s_planted['pivotal_ids']}")
    if not t_p["strategic_abstention"]:
        return fail(f"planted strategic_abstention silent {t_p}")
    honest = t_p.get("honest_counterfactual") or {}
    if honest.get("outcome") != "PASS" or not honest.get("flips_vs_actual"):
        return fail(f"planted honest counterfactual {honest}")

    if s_control["actual"]["outcome"] != "PASS":
        return fail(f"control actual {s_control['actual']}")
    if "TARGET" in s_control["pivotal_ids"]:
        return fail(f"control unexpectedly pivotal {s_control}")
    if t_c["strategic_abstention"] or t_c["pivotal_abstention"]:
        return fail(f"control not silent {t_c}")
    if t_c["implied_stance"] != "aye":
        return fail("control implied stance drifted (sibling not matched)")

    if "TARGET" not in s_prin["pivotal_ids"]:
        return fail("principled sibling not pivotal (shape mismatch with planted)")
    if t_r["strategic_abstention"] or t_r["strategic"]:
        return fail(f"principled flagged strategic {t_r}")
    if t_r["implied_stance"] != "abstain":
        return fail(f"principled implied {t_r['implied_stance']}")

    # Policy id recorded on the live tally object.
    live = tally(
        ["aye", "aye", "nay", "nay", "abstain"],
        quorum=3,
        threshold="majority_of_seated",
        abstention_policy="include_in_denominator",
        n_seats=5,
    )
    if live["policy_id"] != s_planted["policy_id"]:
        return fail(f"policy_id mismatch {live['policy_id']} vs {s_planted['policy_id']}")
    if live["outcome"] != "FAIL":
        return fail(f"hand tally {live}")

    print("SUCCESS:IMP-0347-probe2 planted fires, control silent, principled not strategic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
