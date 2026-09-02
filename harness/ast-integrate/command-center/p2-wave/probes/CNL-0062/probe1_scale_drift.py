#!/usr/bin/env python3
"""Probe 1: scale-drift fixture + approval-as-score identity.

Signal 1: argmax of exact Fraction totals after per-ballot min-max calibration.
Signal 2: pairwise score-margin Condorcet on the same calibrated ballots.
A disagreement in the winner blocks the unit.

Does not read the author's prose; re-tabulates fixtures then checks the
published artifact numbers match the recount.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
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
OUT = HERE / "probe1-scale-drift.raw.json"


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0062-probe1 artifact absent")
        return 1
    try:
        note = json.loads(ART.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0062-probe1 artifact unparseable:{type(exc).__name__}")
        return 1
    if str(note.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0062-probe1 artifact self-declared", note.get("state"))
        return 1
    if "SUCCESS:CNL-0062" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0062-probe1 sentinel absent")
        return 1

    drift = load_fix("scale_drift.json")
    cands = list(drift["candidates"])
    by_id = {b["seat_id"]: b for b in drift["ballots"]}
    src = {c: T.as_frac(by_id["canonical"]["scores"][c]) for c in cands}
    dst = {c: T.as_frac(by_id["drifted"]["scores"][c]) for c in cands}
    affine = T.positive_affine_map(src, dst, cands)
    if affine is None:
        print("FAILED:CNL-0062-probe1 drifted is not a positive affine image of canonical")
        return 1
    a, b = affine

    raw_can = T.tabulate(drift, drift["electorates"]["with_canonical"], calibrate=False)
    raw_dft = T.tabulate(drift, drift["electorates"]["with_drifted"], calibrate=False)
    cal_can = T.tabulate(drift, drift["electorates"]["with_canonical"], calibrate=True)
    cal_dft = T.tabulate(drift, drift["electorates"]["with_drifted"], calibrate=True)

    if not (raw_can["signals_agree"] and raw_dft["signals_agree"] and cal_can["signals_agree"] and cal_dft["signals_agree"]):
        print("FAILED:CNL-0062-probe1 totals/pairwise disagreement")
        return 1
    if raw_can["winner_totals"] == raw_dft["winner_totals"]:
        print("FAILED:CNL-0062-probe1 uncalibrated substitution did not flip winner; fixture is not load-bearing")
        return 1
    if cal_can["winner_totals"] != cal_dft["winner_totals"]:
        print("FAILED:CNL-0062-probe1 calibration failed: identical prefs, different anchors, different winner")
        return 1
    if cal_can["totals"] != cal_dft["totals"]:
        print("FAILED:CNL-0062-probe1 calibrated totals differ for affine-equivalent substitution")
        return 1

    appr = load_fix("approval_identity.json")
    as_score = deepcopy(appr)
    as_score["ballots"] = appr["as_score_ballots"]
    t_appr = T.tabulate(appr, calibrate=True)
    t_score = T.tabulate(as_score, calibrate=True)
    if t_appr["winner_totals"] != t_score["winner_totals"]:
        print("FAILED:CNL-0062-probe1 approval is not score restricted to {0,1}")
        return 1
    if t_appr["totals"] != t_score["totals"]:
        print("FAILED:CNL-0062-probe1 approval/score totals diverge on {0,1} ballots")
        return 1

    published = (((note.get("worked_examples") or {}).get("scale_drift")) or {})
    want = {
        "affine_a": str(a),
        "affine_b": str(b),
        "raw_winner_with_canonical": raw_can["winner_totals"],
        "raw_winner_with_drifted": raw_dft["winner_totals"],
        "calibrated_winner_with_canonical": cal_can["winner_totals"],
        "calibrated_winner_with_drifted": cal_dft["winner_totals"],
        "calibrated_totals": cal_can["totals"],
        "approval_winner": t_appr["winner_totals"],
        "score_on_01_winner": t_score["winner_totals"],
    }
    mismatches = [k for k, v in want.items() if published.get(k) != v]
    if mismatches:
        print("FAILED:CNL-0062-probe1 artifact recount mismatch", mismatches)
        return 1

    snap = {
        "affine": {"a": str(a), "b": str(b)},
        "raw_can": {k: raw_can[k] for k in ("winner_totals", "winner_pairwise", "totals")},
        "raw_dft": {k: raw_dft[k] for k in ("winner_totals", "winner_pairwise", "totals")},
        "cal_can": {k: cal_can[k] for k in ("winner_totals", "winner_pairwise", "totals")},
        "cal_dft": {k: cal_dft[k] for k in ("winner_totals", "winner_pairwise", "totals")},
        "approval": t_appr["totals"],
        "approval_winner": t_appr["winner_totals"],
    }
    OUT.write_text(json.dumps(snap, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "affine_verified=True a={a} b={b} "
        "raw_with_canonical={rc} raw_with_drifted={rd} drift_flips_raw=True "
        "cal_with_canonical={cc} cal_with_drifted={cd} cal_stable=True "
        "signal1=argmax-fraction signal2=pairwise-score-margins signals_agree=True "
        "approval_winner={aw} score_on_01_winner={sw} approval_is_score_restriction=True".format(
            a=a,
            b=b,
            rc=raw_can["winner_totals"],
            rd=raw_dft["winner_totals"],
            cc=cal_can["winner_totals"],
            cd=cal_dft["winner_totals"],
            aw=t_appr["winner_totals"],
            sw=t_score["winner_totals"],
        )
    )
    print("SUCCESS:CNL-0062-probe1 scale-drift and approval-as-score")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
