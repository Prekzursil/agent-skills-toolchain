#!/usr/bin/env python3
"""Probe 2: divergence is reported, never silently resolved; Condorcet cycle named.

Starts from the ballot profile arithmetic (pairwise margins, IRV transfers),
not from an author summary. Both-states control: a mutant that binds IRV as
the default winner must make hides_divergence() fire, while the live report
must stay silent on that detector.
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
    hides_divergence,
    mutant_silent_default,
    textbook_fixtures,
)

OUT = HERE / "probe2-divergence-cycle.raw.json"

# Independent pairwise recount of the constructed cycle (not engine output).
CYCLE_PAIRWISE = {
    "A>B": (6, 3),
    "B>C": (7, 2),
    "C>A": (5, 4),
}


def _fail(msg: str, payload: dict) -> int:
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"FAILED:IMP-0303-probe2 {msg}")
    return 1


def independent_cycle_margins(ballots, candidates):
    """Recount pairwise margins with a fresh nested loop (not pairwise_condorcet)."""
    pref = {a: {b: 0 for b in candidates if b != a} for a in candidates}
    for b in ballots:
        rank = {c: i for i, c in enumerate(b.ranking)}
        for a in candidates:
            for c in candidates:
                if a >= c:
                    continue
                ia, ic = rank[a], rank[c]
                if ia < ic:
                    pref[a][c] += b.weight
                else:
                    pref[c][a] += b.weight
    return {
        f"{a}>{c}": (pref[a][c], pref[c][a])
        for a, c in (("A", "B"), ("B", "C"), ("C", "A"))
    }


def run_checks() -> tuple[bool, dict]:
    errors: list[str] = []
    fixtures = textbook_fixtures()

    tn = fixtures["tennessee-capital"]
    tn_rep = evaluate_all(tn.ballots, tn.candidates)
    winners = tn_rep.winners_by_method
    if winners[RANKED_CHOICE] == winners[PAIRWISE]:
        errors.append("tennessee IRV and Condorcet unexpectedly agree; divergence fixture is dead")
    if not tn_rep.divergent:
        errors.append("tennessee divergent flag False")
    if tn_rep.binding_winner is not None:
        errors.append(f"tennessee silently bound {tn_rep.binding_winner}")
    if tn_rep.owner_action != "SURFACE_DIVERGENCE":
        errors.append(f"tennessee owner_action={tn_rep.owner_action}")
    if tn_rep.agreed_winner is not None:
        errors.append("tennessee agreed_winner set while methods disagree")
    if hides_divergence(tn_rep):
        errors.append("live tennessee report hides divergence")

    mutant = mutant_silent_default(tn_rep, RANKED_CHOICE)
    fired_on_bad = hides_divergence(mutant)
    silent_on_good = not hides_divergence(tn_rep)
    if not fired_on_bad:
        errors.append("negative control: mutant default-IRV did not fire hides_divergence")
    if not silent_on_good:
        errors.append("negative control: detector fired on the live report")
    if mutant.binding_winner != "Knoxville":
        errors.append("mutant should bind IRV Knoxville")
    if winners[PAIRWISE] != "Nashville":
        errors.append("Condorcet winner should remain Nashville on the live report")

    cyc = fixtures["condorcet-cycle-unequal"]
    live_margins = independent_cycle_margins(cyc.ballots, cyc.candidates)
    if live_margins != CYCLE_PAIRWISE:
        errors.append(f"independent cycle margins {live_margins} != {CYCLE_PAIRWISE}")
    cyc_rep = evaluate_all(cyc.ballots, cyc.candidates)
    pw = cyc_rep.by_method[PAIRWISE]
    if pw.status != "CONDORCET_CYCLE" or pw.winner is not None:
        errors.append(f"cycle status={pw.status} winner={pw.winner}")
    if not cyc_rep.cycle_reported:
        errors.append("cycle_reported False")
    if pw.detail.get("cycle") is not True:
        errors.append("pairwise detail.cycle is not True")
    if cyc_rep.binding_winner is not None:
        errors.append("cycle silently bound a winner")
    if not cyc_rep.divergent:
        errors.append("cycle profile should diverge across methods")
    # Completing the cycle with Schulze/Copeland would elect someone; we must not.
    if pw.winner is not None:
        errors.append("cycle completed into a winner")

    agree = fixtures["irv-three-candidate"]
    agree_rep = evaluate_all(agree.ballots, agree.candidates)
    if agree_rep.divergent or agree_rep.agreed_winner != "B":
        errors.append("agreement control failed")
    if hides_divergence(agree_rep):
        errors.append("agreement profile flagged as hidden divergence")

    payload = {
        "probe": "probe2-divergence-cycle",
        "unit_id": "IMP-0303",
        "errors": errors,
        "tennessee": {
            "winners_by_method": winners,
            "divergent": tn_rep.divergent,
            "binding_winner": tn_rep.binding_winner,
            "owner_action": tn_rep.owner_action,
        },
        "cycle": {
            "independent_margins": live_margins,
            "status": pw.status,
            "winner": pw.winner,
            "cycle_reported": cyc_rep.cycle_reported,
            "winners_by_method": cyc_rep.winners_by_method,
        },
        "both_states": {
            "fired_on_bad_state": fired_on_bad,
            "silent_on_good_state": silent_on_good,
            "mutant_binding_winner": mutant.binding_winner,
            "mutant_owner_action": mutant.owner_action,
        },
        "pass": not errors,
    }
    return not errors, payload


def main() -> int:
    ok, payload = run_checks()
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    bs = payload["both_states"]
    print(
        json.dumps(
            {
                "pass": ok,
                "errors": payload["errors"],
                "tennessee_winners": payload["tennessee"]["winners_by_method"],
                "cycle_status": payload["cycle"]["status"],
                "fired_on_bad": bs["fired_on_bad_state"],
                "silent_on_good": bs["silent_on_good_state"],
            }
        )
    )
    if not ok:
        print("FAILED:IMP-0303-probe2 divergence/cycle")
        return 1
    print(
        "divergent=True binding=None cycle=CONDORCET_CYCLE "
        f"fired_on_bad={bs['fired_on_bad_state']} silent_on_good={bs['silent_on_good_state']}"
    )
    print("SUCCESS:IMP-0303-probe2 divergence surfaced; Condorcet cycle reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
