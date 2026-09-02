#!/usr/bin/env python3
"""Probe 2: both-states control + negative control + independent column-major recount.

The scale-drift check is: uncalibrated winner != calibrated winner.
  * SILENT on known-good (mixed approval; calibration is identity)
  * FIRES on planted-bad (affine-stretched scores treated as commensurate)

Negative control, recorded verbatim: on the planted-bad fixture — the state the
check is meant to reject — the check FIRES.

Independent recount: column-major Fraction accumulation in THIS file, not
tabulate.totals_row_major, then compared to the artifact and to pairwise.
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import tabulate as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0062-cardinal-ballots-approval-and-score-and-cross-participant-.md"
)
OUT = HERE / "probe2-both-states.raw.json"


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def column_major_totals(fixture: dict, calibrate: bool) -> dict[str, Fraction]:
    """Recount that walks candidates outer, ballots inner — not row-major."""
    candidates, ballots, _, _ = T.load_ballots(fixture, None)
    totals = {c: Fraction(0) for c in candidates}
    for c in candidates:
        for b in ballots:
            if calibrate:
                cal, _ = T.calibrate_ballot(b["raw"], candidates)
            else:
                cal = b["raw"]
            totals[c] += b["weight"] * cal[c]
    return totals


def drift_check(fixture: dict) -> dict:
    raw = T.tabulate(fixture, calibrate=False)
    cal = T.tabulate(fixture, calibrate=True)
    fired = raw["winner_totals"] != cal["winner_totals"]
    col_raw = column_major_totals(fixture, False)
    col_cal = column_major_totals(fixture, True)
    if col_raw != raw["totals_exact"] or col_cal != cal["totals_exact"]:
        raise AssertionError("column-major recount disagrees with row-major")
    if not raw["signals_agree"] or not cal["signals_agree"]:
        raise AssertionError("pairwise/totals disagreement")
    return {
        "fired": fired,
        "raw_winner": raw["winner_totals"],
        "cal_winner": cal["winner_totals"],
        "raw_totals": raw["totals"],
        "cal_totals": cal["totals"],
        "column_major_cal": {c: str(col_cal[c]) for c in cal["candidates"]},
    }


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0062-probe2 artifact absent")
        return 1
    try:
        note = json.loads(ART.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0062-probe2 artifact unparseable:{type(exc).__name__}")
        return 1
    if str(note.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0062-probe2 artifact self-declared", note.get("state"))
        return 1

    good = drift_check(load_fix("known_good.json"))
    bad = drift_check(load_fix("planted_bad.json"))
    if good["fired"]:
        print("FAILED:CNL-0062-probe2 known-good must be SILENT, fired")
        return 1
    if not bad["fired"]:
        print("FAILED:CNL-0062-probe2 planted-bad must FIRE, was silent")
        return 1

    weight_reject = "NOT-RUN"
    poisoned = load_fix("known_good.json")
    poisoned["ballots"][0]["weight"] = 2
    try:
        T.tabulate(poisoned, calibrate=True)
        print("FAILED:CNL-0062-probe2 weight!=1 without provenance was accepted")
        return 1
    except ValueError as exc:
        if "weight_provenance" not in str(exc):
            print("FAILED:CNL-0062-probe2 wrong rejection", exc)
            return 1
        weight_reject = f"FIRES:{exc}"

    published = note.get("both_states") or {}
    if published.get("known_good_fired") is not False:
        print("FAILED:CNL-0062-probe2 artifact known_good_fired mismatch")
        return 1
    if published.get("planted_bad_fired") is not True:
        print("FAILED:CNL-0062-probe2 artifact planted_bad_fired mismatch")
        return 1
    if published.get("planted_bad_raw_winner") != bad["raw_winner"]:
        print("FAILED:CNL-0062-probe2 independent recount raw winner mismatch")
        return 1
    if published.get("planted_bad_cal_winner") != bad["cal_winner"]:
        print("FAILED:CNL-0062-probe2 independent recount cal winner mismatch")
        return 1
    if published.get("negative_control_on_reject_state") != "FIRES":
        print("FAILED:CNL-0062-probe2 negative control not recorded as FIRES")
        return 1

    snap = {
        "known_good": good,
        "planted_bad": bad,
        "weight_reject": weight_reject,
        "both_states": True,
        "negative_control_on_reject_state": "FIRES",
    }
    OUT.write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "known_good fired={gf} silent={gs} raw={gr} cal={gc} "
        "planted_bad fired={bf} silent={bs} raw={br} cal={bc} "
        "negative_control_on_reject_state=FIRES both_states=True "
        "independent_column_major_agrees=True weight_without_provenance={wr}".format(
            gf=good["fired"],
            gs=not good["fired"],
            gr=good["raw_winner"],
            gc=good["cal_winner"],
            bf=bad["fired"],
            bs=not bad["fired"],
            br=bad["raw_winner"],
            bc=bad["cal_winner"],
            wr=weight_reject,
        )
    )
    print("SUCCESS:CNL-0062-probe2 both-states and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
