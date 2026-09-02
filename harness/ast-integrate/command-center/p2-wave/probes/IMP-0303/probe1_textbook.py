#!/usr/bin/env python3
"""Probe 1: each method against a published / hand-computed worked example.

Independently restates the Wikipedia Tennessee counts and the cardinal
worked examples, then checks tools/council/vote/ballots.py against those
numbers — not against the author's summary string.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.vote.ballots import (  # noqa: E402
    APPROVAL,
    PAIRWISE,
    RANKED_CHOICE,
    SCORE,
    evaluate_all,
    textbook_fixtures,
)

OUT = HERE / "probe1-textbook.raw.json"

# Hand-computed from the Wikipedia Tennessee capital profile (100 ballots).
TN_IRV_ROUNDS = (
    {"Memphis": 42, "Nashville": 26, "Knoxville": 17, "Chattanooga": 15},
    {"Memphis": 42, "Nashville": 26, "Knoxville": 32},
    {"Memphis": 42, "Knoxville": 58},
)
TN_PAIRWISE_NASHVILLE = {
    "Memphis": (58, 42),
    "Chattanooga": (68, 32),
    "Knoxville": (68, 32),
}
TN_BORDA = {"Nashville": 194, "Chattanooga": 173, "Memphis": 126, "Knoxville": 107}
TN_APPROVAL = {"Nashville": 68, "Chattanooga": 58, "Memphis": 42, "Knoxville": 32}
SCORE_TOTALS = {"A": 14, "B": 19, "C": 9}
APPROVAL_TOTALS = {"Andrea": 3, "Brad": 2, "Carter": 1}
IRV3_ROUNDS = (
    {"A": 4, "B": 3, "C": 2},
    {"A": 4, "B": 5},
)


def _fail(msg: str, payload: dict) -> int:
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"FAILED:IMP-0303-probe1 {msg}")
    return 1


def run_checks() -> tuple[bool, dict]:
    fixtures = textbook_fixtures()
    rows: dict[str, dict] = {}
    errors: list[str] = []

    tn = fixtures["tennessee-capital"]
    tn_rep = evaluate_all(tn.ballots, tn.candidates)
    irv = tn_rep.by_method[RANKED_CHOICE]
    rounds = irv.detail.get("rounds") or []
    live_rounds = [r["counts"] for r in rounds]
    if live_rounds != list(TN_IRV_ROUNDS):
        errors.append(f"tennessee IRV rounds {live_rounds} != {list(TN_IRV_ROUNDS)}")
    if irv.winner != "Knoxville":
        errors.append(f"tennessee IRV winner {irv.winner!r}")

    pw = tn_rep.by_method[PAIRWISE]
    matrix = pw.detail.get("pairwise_matrix") or {}
    for rival, (win, lose) in TN_PAIRWISE_NASHVILLE.items():
        key = f"Nashville>{rival}"
        cell = matrix.get(key) or {}
        if cell.get("for") != win or cell.get("against") != lose or not cell.get("beats"):
            errors.append(f"tennessee pairwise {key} {cell} want for={win} against={lose}")
    if pw.winner != "Nashville" or pw.status != "CONDORCET_WINNER":
        errors.append(f"tennessee Condorcet {pw.winner} {pw.status}")

    sc = tn_rep.by_method[SCORE]
    if sc.totals != TN_BORDA or sc.winner != "Nashville":
        errors.append(f"tennessee score {sc.totals} winner={sc.winner}")
    ap = tn_rep.by_method[APPROVAL]
    if ap.totals != TN_APPROVAL or ap.winner != "Nashville":
        errors.append(f"tennessee approval {ap.totals} winner={ap.winner}")
    rows["tennessee-capital"] = tn_rep.to_dict()

    irv3 = fixtures["irv-three-candidate"]
    irv3_rep = evaluate_all(irv3.ballots, irv3.candidates)
    live_i3 = [r["counts"] for r in irv3_rep.by_method[RANKED_CHOICE].detail.get("rounds") or []]
    if live_i3 != list(IRV3_ROUNDS):
        errors.append(f"irv3 rounds {live_i3}")
    if irv3_rep.winners_by_method[RANKED_CHOICE] != "B":
        errors.append("irv3 winner not B")
    rows["irv-three-candidate"] = irv3_rep.to_dict()

    scf = fixtures["score-range-0-9"]
    sc_rep = evaluate_all(scf.ballots, scf.candidates)
    live_sc = sc_rep.by_method[SCORE]
    if live_sc.totals != SCORE_TOTALS or live_sc.winner != "B":
        errors.append(f"score-range {live_sc.totals} winner={live_sc.winner}")
    if sc_rep.by_method[RANKED_CHOICE].status != "NO_ORDINAL_BALLOTS":
        errors.append("score-range invented rankings")
    rows["score-range-0-9"] = sc_rep.to_dict()

    apf = fixtures["approval-andrea"]
    ap_rep = evaluate_all(apf.ballots, apf.candidates)
    live_ap = ap_rep.by_method[APPROVAL]
    if live_ap.totals != APPROVAL_TOTALS or live_ap.winner != "Andrea":
        errors.append(f"approval {live_ap.totals} winner={live_ap.winner}")
    if live_ap.totals.get("Andrea") != 3:
        errors.append("approval Andrea count")
    rows["approval-andrea"] = ap_rep.to_dict()

    payload = {
        "probe": "probe1-textbook",
        "unit_id": "IMP-0303",
        "errors": errors,
        "reports": rows,
        "pass": not errors,
    }
    return not errors, payload


def main() -> int:
    ok, payload = run_checks()
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"pass": ok, "errors": payload["errors"], "fixtures": list(payload["reports"])}))
    if not ok:
        print("FAILED:IMP-0303-probe1 textbook winners")
        return 1
    print("tennessee IRV=Knoxville Condorcet=Nashville Borda=Nashville approval=Nashville")
    print("score-range B=19/14/9 approval Andrea=3 irv3 B after C-transfer")
    print("SUCCESS:IMP-0303-probe1 each method against a published worked example")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
