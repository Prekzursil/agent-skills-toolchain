#!/usr/bin/env python3
"""Probe 2: independent recount + both-states leak control.

Mechanically different from probe 1:
  * Re-parses WORK-UNIT-CATALOG.json CNL-0042.question_or_target (regex)
  * Re-tabulates roster family=GENERATIVE
  * Runs leak_check on known-good (must be SILENT) and planted-bad (must FIRE)
    for every record, plus the drop_idea suppression mutant.

Does not read the author's prose; it re-derives counts and re-runs the detector.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import runtime as R  # noqa: E402
import schedules as S  # noqa: E402

NOTE = (
    C.REPO
    / "command-center/design/council/CNL-0042-executable-runtime-semantics-for-the-7-generative-protocol.md"
)


def main() -> int:
    unit = C.catalog_unit()
    q = str(unit.get("question_or_target") or "")
    named = C.named_from_catalog_question(q)
    named_ids = [p for p, _ in named]
    roster = C.roster_generative()
    roster_ids = [r["id"] for r in roster]
    decoys = C.decoy_ids()

    both = []
    fail = False
    for rec in roster:
        good = R.leak_check(rec, S.good_schedule(rec))
        bad = R.leak_check(rec, S.planted_bad_schedule(rec))
        supp = R.leak_check(rec, S.suppression_bad_schedule(rec))
        early = R.leak_check(rec, S.critique_before_gate_schedule(rec))
        silent_good = good["silent"] is True and good["fired"] is False
        fires_bad = bad["fired"] is True and "CRITIQUE_ACT_IN_GENERATE" in bad["codes"]
        fires_drop = supp["fired"] is True and "IDEA_COUNT_SUPPRESSION" in supp["codes"]
        fires_early = early["fired"] is True and "CRITIQUE_BEFORE_GATE" in early["codes"]
        row = {
            "record_id": rec["id"],
            "silent_on_good": silent_good,
            "fired_on_bad": fires_bad,
            "fired_on_suppression": fires_drop,
            "fired_on_before_gate": fires_early,
            "good_idea_count": good["idea_count"],
            "bad_codes": bad["codes"],
            "suppression_codes": supp["codes"],
            "before_gate_codes": early["codes"],
        }
        both.append(row)
        if not (silent_good and fires_bad and fires_drop and fires_early):
            fail = True

    counts_ok = (
        named_ids == list(C.NAMED_IDS)
        and roster_ids == list(C.NAMED_IDS)
        and len(named_ids) == C.EXPECTED_N
        and not any(d in named_ids or d in roster_ids for d in decoys)
    )
    if not counts_ok:
        print(
            "FAILED:CNL-0042-probe2 recount "
            f"named={named_ids} roster={roster_ids} decoys={decoys}"
        )
        fail = True

    # Negative control, recorded verbatim: the check on the state it rejects.
    p26 = next(r for r in roster if r["id"] == "P26")
    neg = R.leak_check(p26, S.planted_bad_schedule(p26))
    negative_control = {
        "state_rejected": "CRITIQUE speech act (score) inside a GENERATE round of P26",
        "check": "runtime.leak_check",
        "fired": neg["fired"],
        "codes": neg["codes"],
        "verbatim_findings": neg["findings"],
    }

    if NOTE.is_file():
        note = json.loads(NOTE.read_text(encoding="utf-8"))
        recorded_n = int((note.get("census") or {}).get("family_n") or -1)
        if recorded_n != C.EXPECTED_N:
            print(f"FAILED:CNL-0042-probe2 note family_n drift {recorded_n}")
            fail = True
        rec_ids = [v.get("record_id") for v in (note.get("per_record") or [])]
        if rec_ids and rec_ids != roster_ids:
            print(f"FAILED:CNL-0042-probe2 note id drift {rec_ids}")
            fail = True
        blob = json.dumps(note)
        if "SUCCESS:CNL-0042" not in blob:
            print("FAILED:CNL-0042-probe2 sentinel missing")
            fail = True

    payload = {
        "probe": "probe2-both-states",
        "unit_id": "CNL-0042",
        "independent_named_ids": named_ids,
        "independent_roster_ids": roster_ids,
        "family_n": len(roster_ids),
        "decoy_excluded": decoys,
        "both_states": both,
        "negative_control": negative_control,
        "all_silent_on_good": all(r["silent_on_good"] for r in both),
        "all_fired_on_bad": all(r["fired_on_bad"] for r in both),
        "pass": (not fail)
        and all(r["silent_on_good"] and r["fired_on_bad"] for r in both),
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"silent_on_good={payload['all_silent_on_good']} "
        f"fired_on_bad={payload['all_fired_on_bad']} "
        f"n={len(roster_ids)} decoy_excluded={decoys}"
    )
    print(
        "NEGATIVE_CONTROL_VERBATIM "
        + json.dumps(negative_control, sort_keys=True)
    )
    if fail:
        print("FAILED:CNL-0042-probe2 both-states / independent recount")
        return 1
    print("SUCCESS:CNL-0042-probe2 both-states control and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
