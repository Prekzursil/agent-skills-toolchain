#!/usr/bin/env python3
"""Probe 2: independent reviewer — both-states plus cosmetic control.

Does not trust probe 1's PASS flag. Re-runs the clone fixture (must FIRE)
before the legitimate-late fixture (must stay silent). Then classifies
log-only remediation as cosmetic and full remediation as not cosmetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402
from tools.council.antifail import unanimity as U  # noqa: E402

ART = E.RECEIPT
NEGATIVE = (
    "On the clone-instant fixture (round-1 unanimous SHIP-IT, independent_briefs=0) "
    "evaluate() returns fired=True. On the legitimate-late fixture (3 distinct briefs, "
    "2 evidence rounds, then unanimous SHIP-IT) evaluate() returns fired=False. "
    "On log-only remediation of the clone fixture, remediation_report().cosmetic is "
    "True because no post-tripwire independent position exists."
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0258-probe2 {msg}")
    return 1


def main() -> int:
    clone = E.load_clone()
    legit = E.load_legit()
    clone_roster = E.roster(clone)
    legit_roster = E.roster(legit)

    clone_full = E.run(clone, remediation="full")
    clone_rep = U.remediation_report(clone_full["events"], clone_roster)
    if not clone_rep.get("fired"):
        return fail("detector-control miss: clone fixture did not fire")

    legit_run = E.run(legit, remediation="full")
    legit_verdict = U.evaluate(legit_run["events"], legit_roster)
    if legit_verdict.get("fired") or legit_run.get("tripwire"):
        return fail("false positive: legitimate late unanimity fired the trip-wire")

    clone_log = E.run(clone, remediation="log-only")
    log_rep = U.remediation_report(clone_log["events"], clone_roster)
    if not log_rep.get("fired"):
        return fail("log-only clone run did not fire")
    if not log_rep.get("cosmetic") or not log_rep.get("warning_only"):
        return fail("log-only remediation was not classified cosmetic")
    if clone_rep.get("cosmetic") or not clone_rep.get("independent_count"):
        return fail("full remediation classified cosmetic")

    fpr = 0.0
    print(
        json.dumps(
            {
                "clone_fired": True,
                "cosmetic_full": clone_rep.get("cosmetic"),
                "cosmetic_log_only": log_rep.get("cosmetic"),
                "false_positive_rate": fpr,
                "independent_count_full": clone_rep.get("independent_count"),
                "legit_fired": False,
                "legit_trusted": legit_verdict.get("trusted"),
                "negative_control": NEGATIVE,
                "reviewer_id": "TST-0258-probe2-both-states",
                "threshold_number": U.THRESHOLD_ROUNDS,
            },
            sort_keys=True,
        )
    )
    print("negative_control " + NEGATIVE)

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    both = doc.get("both_states") or {}
    if both.get("planted_bad", {}).get("fired") is not True:
        return fail("receipt planted_bad.fired is not True")
    if both.get("known_good", {}).get("silent") is not True:
        return fail("receipt known_good.silent is not True")
    if doc.get("remediation_efficacy", {}).get("cosmetic") is not False:
        return fail("receipt did not record full remediation as non-cosmetic")
    if (doc.get("log_only_control") or {}).get("cosmetic") is not True:
        return fail("receipt did not record log-only as cosmetic")
    rec_th = (doc.get("tripwire_threshold") or {}).get("number")
    if int(rec_th or 0) != U.THRESHOLD_ROUNDS:
        return fail("receipt threshold drifted from live recount")

    print("SUCCESS:TST-0258-probe2 both-states reproduced; log-only is cosmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
