#!/usr/bin/env python3
"""Probe 2: abstention / no-show on the live engine, plus independent IRV recount.

Mechanically different from probe 1 (remove a ballot; do not rewrite rankings).
Re-derives the IRV textbook and no-show winners with independent_irv() which
does not call ranked_choice().
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import profiles as P  # noqa: E402

OUT = HERE / "probe2-abstention-noshow.raw.json"


def _as_dicts(ballots) -> list[dict]:
    return [b.to_dict() for b in ballots]


def main() -> int:
    errors: list[str] = []
    cen = E.census()
    det = E.detector_census()
    if not cen["engine_present"]:
        print("FAILED:ADV-0098-probe2 engine missing")
        return 1

    honest, c3 = P.irv_noshow_honest()
    abstain, _ = P.irv_noshow_abstain()
    live_h = E.run(E.RANKED_CHOICE, honest, c3)
    live_a = E.run(E.RANKED_CHOICE, abstain, c3)
    ind_h = E.independent_irv(honest, c3)
    ind_a = E.independent_irv(abstain, c3)
    if ind_h["winner"] != live_h.winner:
        errors.append(
            f"independent IRV disagree honest live={live_h.winner} ind={ind_h['winner']}"
        )
    if ind_a["winner"] != live_a.winner:
        errors.append(
            f"independent IRV disagree abstain live={live_a.winner} ind={ind_a['winner']}"
        )
    a_true = ("A", "B", "C")
    noshow_helps = E.prefers(a_true, live_a.winner, live_h.winner)
    if live_h.winner != "C" or live_a.winner != "B" or not noshow_helps:
        errors.append(
            f"irv-noshow control failed honest={live_h.winner} abstain={live_a.winner} "
            f"helps={noshow_helps}"
        )

    # Reviewer recount of probe-1 textbook IRV (not copied from probe-1 output).
    t_h, _ = P.irv_compromise_honest()
    t_s, _ = P.irv_compromise_strategic()
    t_live_h = E.run(E.RANKED_CHOICE, t_h, c3)
    t_live_s = E.run(E.RANKED_CHOICE, t_s, c3)
    t_ind_h = E.independent_irv(t_h, c3)
    t_ind_s = E.independent_irv(t_s, c3)
    if t_ind_h["winner"] != t_live_h.winner or t_ind_s["winner"] != t_live_s.winner:
        errors.append("independent IRV disagree on textbook compromise")
    if t_live_h.winner != "C" or t_live_s.winner != "B":
        errors.append(
            f"textbook IRV recount honest={t_live_h.winner} strategic={t_live_s.winner}"
        )

    # Two-candidate: split the A-bloc into individuals; one A abstains -> 2-2.
    two_indiv = [
        E.ballot("a1", ranking=("A", "B"), scores={"A": 1, "B": 0}, approved=("A",)),
        E.ballot("a2", ranking=("A", "B"), scores={"A": 1, "B": 0}, approved=("A",)),
        E.ballot("a3", ranking=("A", "B"), scores={"A": 1, "B": 0}, approved=("A",)),
        E.ballot("b1", ranking=("B", "A"), scores={"B": 1, "A": 0}, approved=("B",)),
        E.ballot("b2", ranking=("B", "A"), scores={"B": 1, "A": 0}, approved=("B",)),
    ]
    two_abs = [b for b in two_indiv if b.voter_id != "a3"]
    c2 = ("A", "B")
    two_rows = []
    for method in (E.RANKED_CHOICE, E.PAIRWISE, E.SCORE, E.APPROVAL):
        h = E.run(method, two_indiv, c2)
        a = E.run(method, two_abs, c2)
        helps = E.prefers(("A", "B"), a.winner, h.winner)
        two_rows.append(
            {
                "method": method,
                "honest_winner": h.winner,
                "abstain_winner": a.winner,
                "abstainer_improved": helps,
                "honest_status": h.status,
                "abstain_status": a.status,
            }
        )
        if h.winner != "A":
            errors.append(f"two-candidate {method} honest winner {h.winner} != A")
        if helps:
            errors.append(
                f"negative-control-two-candidate-abstain: {method} helped an A-voter "
                "by not showing; enumerator/engine unexpected"
            )

    uni, _ = P.unanimous_a()
    uni_abs = uni[1:]
    uni_h = E.run(E.RANKED_CHOICE, uni, c3)
    uni_a = E.run(E.RANKED_CHOICE, uni_abs, c3)
    if uni_h.winner != "A" or uni_a.winner != "A":
        errors.append(f"unanimous IRV honest={uni_h.winner} abstain={uni_a.winner}")
    if E.prefers(("A", "B", "C"), uni_a.winner, uni_h.winner):
        errors.append("unanimous abstention unexpectedly improved")

    payload = {
        "probe": "probe2-abstention-noshow",
        "unit_id": "ADV-0098",
        "census": cen,
        "detector": det,
        "irv_noshow": {
            "honest_winner_live": live_h.winner,
            "abstain_winner_live": live_a.winner,
            "honest_winner_independent": ind_h["winner"],
            "abstain_winner_independent": ind_a["winner"],
            "independent_rounds_honest": ind_h["rounds"],
            "independent_rounds_abstain": ind_a["rounds"],
            "a_bloc_true_ranking": list(a_true),
            "abstention_improves_a_bloc": noshow_helps,
            "honest_ballots": _as_dicts(honest),
            "abstain_ballots": _as_dicts(abstain),
        },
        "textbook_irv_reviewer_recount": {
            "honest_live": t_live_h.winner,
            "strategic_live": t_live_s.winner,
            "honest_independent": t_ind_h["winner"],
            "strategic_independent": t_ind_s["winner"],
            "independent_rounds_honest": t_ind_h["rounds"],
            "independent_rounds_strategic": t_ind_s["rounds"],
        },
        "two_candidate_abstain": two_rows,
        "unanimous_abstain": {
            "honest": uni_h.winner,
            "abstain": uni_a.winner,
        },
        "controls": {
            "irv_noshow_reproduced": noshow_helps
            and live_h.winner == "C"
            and live_a.winner == "B",
            "independent_matches_live": (
                ind_h["winner"] == live_h.winner and ind_a["winner"] == live_a.winner
            ),
            "two_candidate_abstain_does_not_help_majority": all(
                not r["abstainer_improved"] for r in two_rows
            ),
            "detector_fired_on_noshow": det["detects_noshow"],
        },
        "errors": errors,
        "ok": not errors,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "irv_noshow_honest": live_h.winner,
                "irv_noshow_abstain": live_a.winner,
                "helps": noshow_helps,
                "independent_match": payload["controls"]["independent_matches_live"],
                "textbook_independent": {
                    "honest": t_ind_h["winner"],
                    "strategic": t_ind_s["winner"],
                },
                "detector_present": det["detector_module_present"],
                "errors": errors,
            }
        )
    )
    if errors:
        print("FAILED:ADV-0098-probe2 " + "; ".join(errors))
        return 1
    print(
        "CONTROL_VERBATIM=IRV no-show 5 A>B>C / 4 B>C>A / 3 C>A>B / 2 C>B>A elects C. "
        "Two A-voters abstain (a-bloc weight 3) elects B. A-voters rank A>B>C so B>C "
        "and abstaining beats honest voting. Independent IRV (no ranked_choice call) "
        "matches the live engine. Two-candidate 3 A vs 2 B: one A abstention does not "
        "help the abstainer. No no-show detector fired."
    )
    print("SUCCESS:ADV-0098-probe2 abstention-noshow independent-irv-recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
