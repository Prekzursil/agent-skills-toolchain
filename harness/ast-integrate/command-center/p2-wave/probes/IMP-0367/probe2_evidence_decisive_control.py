#!/usr/bin/env python3
"""Named probe 2: evidence-decisive must stabilise at low N; do not retune N.

Negative control (must FIRE on the bad state):
  * n-modulated aggregator on the evidence-decisive fixture still moves with N.
    Production evaluate_question must report protocol_is_n_sensitive and must
    NOT call tune_until_stable.
  * tune_until_stable on the n-sensitive curve collapses distinct decisions to 1.
    Production majority sweep must still publish the flips.

Both-states (must be SILENT on the good state):
  * majority / retune=False on the evidence-decisive fixture is low-N stable
    and protocol_is_n_sensitive is false.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import scenario as S  # noqa: E402
from council.sensitivity import (  # noqa: E402
    AGG_MAJORITY,
    AGG_N_MODULATED,
    LOW_N_MAX,
    evaluate_question,
    load_question,
    public_row,
    tune_until_stable,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0367-probe2 {msg}")
    return 1


def main() -> int:
    if not S.MODULE.is_file():
        return fail("tools/council/sensitivity.py missing")
    doc = S.require_receipt()
    by_id = S.public_by_id(doc)
    rec_dec = by_id.get("Q-evidence-decisive") or {}
    rec_ns = by_id.get("Q-n-sensitive") or {}

    good = evaluate_question(
        load_question(S.FIX_DECISIVE), aggregator=AGG_MAJORITY, retune=False
    )
    if good.get("retuned") is True:
        return fail("production evidence-decisive retuned")
    if not good.get("low_n_stable"):
        return fail(
            f"evidence-decisive not low-N stable N*={good['stabilisation']['stabilisation_n']}"
        )
    if int(good["stabilisation"]["stabilisation_n"]) > LOW_N_MAX:
        return fail("evidence-decisive N* above LOW_N_MAX on majority")
    if good.get("protocol_is_n_sensitive") is True:
        return fail("majority evidence-decisive flagged protocol_is_n_sensitive")
    if rec_dec.get("protocol_is_n_sensitive") is True:
        return fail("receipt flags protocol_is_n_sensitive on the good fixture")
    if rec_dec.get("low_n_stable") is not True:
        return fail("receipt evidence-decisive low_n_stable is not true")

    mutant = evaluate_question(
        load_question(S.FIX_DECISIVE), aggregator=AGG_N_MODULATED, retune=False
    )
    if mutant.get("retuned") is True:
        return fail("n-modulated path retuned instead of reporting N-sensitivity")
    if not mutant.get("protocol_is_n_sensitive"):
        return fail(
            "n-modulated evidence-decisive did not report protocol_is_n_sensitive"
        )
    if mutant.get("finding") != "protocol-n-sensitive-not-tuned":
        return fail(f"n-modulated finding={mutant.get('finding')}")
    if len(set(p["decision"] for p in mutant["published_curve"])) < 2:
        return fail("n-modulated curve has no N-dependence to report")
    tuned_mutant = evaluate_question(
        load_question(S.FIX_DECISIVE), aggregator=AGG_N_MODULATED, retune=True
    )
    if tuned_mutant.get("retuned") is not True:
        return fail("retune=True did not set retuned")
    if len(set(p["decision"] for p in tuned_mutant["published_curve"])) != 1:
        return fail("tune_until_stable failed to collapse the n-modulated curve")
    if tuned_mutant.get("finding") != "protocol-n-sensitive-WAS-TUNED":
        return fail(f"retuned finding={tuned_mutant.get('finding')}")

    nsens = evaluate_question(
        load_question(S.FIX_NSENS), aggregator=AGG_MAJORITY, retune=False
    )
    pub = public_row(nsens)
    if pub["n_sensitive"] is not True:
        return fail("n-sensitive fixture not n_sensitive on production path")
    if pub["retuned"] is True:
        return fail("n-sensitive production retuned")
    if len(pub["curve"]) != 7:
        return fail(f"n-sensitive published {len(pub['curve'])} points want=7 (not tuned)")
    if rec_ns.get("n_sensitive") is not True:
        return fail("receipt n-sensitive row lost n_sensitive")
    if int(rec_ns.get("flip_count") or 0) < 1:
        return fail("receipt n-sensitive flip_count < 1")
    collapsed = tune_until_stable(nsens["published_curve"])
    if len({p["decision"] for p in collapsed}) != 1:
        return fail("tune_until_stable control did not collapse n-sensitive curve")
    if len(collapsed) == len(nsens["published_curve"]):
        return fail("tune_until_stable dropped nothing; control is silent in both states")

    nc = None
    for item in doc.get("negative_controls") or []:
        if item.get("id") == "IMP-0367-evidence-decisive-no-retune":
            nc = item
            break
    if not isinstance(nc, dict):
        return fail("receipt missing negative control IMP-0367-evidence-decisive-no-retune")
    if nc.get("fired_on_bad_state") is not True:
        return fail("negative control fired_on_bad_state is not true")
    if nc.get("silent_on_good_state") is not True:
        return fail("negative control silent_on_good_state is not true")

    print(
        json.dumps(
            {
                "probe": "probe2-evidence-decisive-control",
                "unit_id": "IMP-0367",
                "pass": True,
                "silent_on_good": True,
                "fired_on_n_modulated": True,
                "did_not_retune_production": True,
                "good_N_star": good["stabilisation"]["stabilisation_n"],
                "mutant_finding": mutant.get("finding"),
                "mutant_distinct": sorted(
                    {p["decision"] for p in mutant["published_curve"]}
                ),
                "tune_collapsed_points": len(collapsed),
                "n_sensitive_published_points": len(pub["curve"]),
            },
            sort_keys=True,
        )
    )
    print(
        "good_N*="
        f"{good['stabilisation']['stabilisation_n']} "
        f"mutant_finding={mutant.get('finding')} "
        f"tune_len={len(collapsed)} published_nsens={len(pub['curve'])}"
    )
    print("SUCCESS:IMP-0367-probe2 evidence-decisive low-N; no retune")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
