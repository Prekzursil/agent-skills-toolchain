"""IMP-0303 probe 1: each method against a published worked example.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0303/probe1_textbook.py
Exit 0 iff the live tools/council/vote/ballots module reproduces, on the
textbook fixtures: Tennessee capital (42/26/15/17) IRV elects Knoxville while
pairwise Condorcet, Borda score and approval all elect Nashville (IRV 58-42
after the Chattanooga transfer; Nashville pairwise 68-32 / 58-42 / 58-42);
the 9-ballot IRV three-candidate example transfers C's votes to B; the
score fixture totals B=19 / A=14 / C=9; the approval fixture elects Andrea
with 3 approvals.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council" / "vote"))
import ballots as B  # noqa: E402

fx = B.textbook_fixtures()
errors = []

tn = fx["tennessee-capital"]
tn_winners = {
    "ranked-choice": B.ranked_choice(tn.ballots, tn.candidates).winner,
    "pairwise-condorcet": B.pairwise_condorcet(tn.ballots, tn.candidates).winner,
    "score": B.score(tn.ballots, tn.candidates).winner,
    "approval": B.approval(tn.ballots, tn.candidates).winner,
}
if tn_winners["ranked-choice"] != "Knoxville":
    errors.append(f"tennessee IRV {tn_winners['ranked-choice']}")
if {tn_winners["pairwise-condorcet"], tn_winners["score"], tn_winners["approval"]} != {"Nashville"}:
    errors.append(f"tennessee others {tn_winners}")

irv3 = fx["irv-three-candidate"]
irv3_res = B.ranked_choice(irv3.ballots, irv3.candidates)
if irv3_res.winner != "B":
    errors.append(f"irv3 winner {irv3_res.winner}")

sc = fx["score-range-0-9"]
sc_res = B.score(sc.ballots, sc.candidates)
totals = sc_res.totals
if not (totals.get("B") == 19 and totals.get("A") == 14 and totals.get("C") == 9):
    errors.append(f"score totals {totals}")

ap = fx["approval-andrea"]
ap_res = B.approval(ap.ballots, ap.candidates)
if ap_res.winner != "Andrea" or ap_res.totals.get("Andrea") != 3:
    errors.append(f"approval {ap_res.winner} {ap_res.totals}")

checks = {
    "tennessee_irv_knoxville": tn_winners["ranked-choice"] == "Knoxville",
    "tennessee_others_nashville": tn_winners["pairwise-condorcet"] == tn_winners["score"] == tn_winners["approval"] == "Nashville",
    "tennessee_divergent": len(set(tn_winners.values())) > 1,
    "irv3_transfer_elects_B": irv3_res.winner == "B",
    "score_totals_19_14_9": totals == {"A": 14, "B": 19, "C": 9},
    "approval_andrea_3": ap_res.totals.get("Andrea") == 3,
    "no_errors": not errors,
}
ok = all(checks.values())
out = {"probe": "probe1-textbook", "unit_id": "IMP-0303",
       "fixtures": sorted(fx),
       "tennessee_winners": tn_winners,
       "irv3_winner": irv3_res.winner,
       "score_totals": totals,
       "approval_totals": ap_res.totals,
       "errors": errors,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-textbook.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0303-probe1 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0303-probe1 tennessee IRV=Knoxville vs Condorcet/score/approval=Nashville; all textbook arithmetic holds")
