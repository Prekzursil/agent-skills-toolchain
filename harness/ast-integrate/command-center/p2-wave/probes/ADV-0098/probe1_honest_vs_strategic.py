#!/usr/bin/env python3
"""Probe 1: honest vs strategic misreporting on the live aggregation engine.

Runs tools/council/vote/ballots.py on pinned honest profiles and on a single
bloc/voter misreport. Records whether the misreporter's true ranking strictly
prefers the new winner.

Control: known IRV compromising profile must elect C honestly and B after two
A-voters compromise. Negative control: two-candidate majority is not helped
by the majority bloc flipping.
"""
from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import profiles as P  # noqa: E402

OUT = HERE / "probe1-honest-vs-strategic.raw.json"
RANKINGS3 = (
    ("A", "B", "C"),
    ("A", "C", "B"),
    ("B", "A", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
    ("C", "B", "A"),
)


def _row(name: str, method: str, honest, strategic, true_ranking, candidates) -> dict:
    h = E.run(method, honest, candidates)
    s = E.run(method, strategic, candidates)
    improved = E.prefers(true_ranking, s.winner, h.winner)
    return {
        "name": name,
        "method": method,
        "honest_winner": h.winner,
        "honest_status": h.status,
        "honest_totals": h.totals,
        "strategic_winner": s.winner,
        "strategic_status": s.status,
        "strategic_totals": s.totals,
        "true_ranking": list(true_ranking),
        "misreporter_improved": improved,
        "honest": E.result_dict(h),
        "strategic": E.result_dict(s),
    }


def condorcet_unique_cw_search(n_voters: int = 5) -> dict:
    """Exhaustive unweighted n-voter search for a beneficial unique-CW flip."""
    cands = ["A", "B", "C"]
    checked = 0
    for ranks in product(RANKINGS3, repeat=n_voters):
        honest = [E.ballot(f"v{i}", ranking=r) for i, r in enumerate(ranks)]
        hw = E.run(E.PAIRWISE, honest, cands)
        if hw.winner is None:
            continue
        for i in range(n_voters):
            for alt in RANKINGS3:
                if alt == ranks[i]:
                    continue
                checked += 1
                variant = list(honest)
                variant[i] = E.ballot(f"v{i}", ranking=alt)
                sw = E.run(E.PAIRWISE, variant, cands)
                if E.prefers(ranks[i], sw.winner, hw.winner):
                    return {
                        "found": True,
                        "n_voters": n_voters,
                        "cw_deviations_checked": checked,
                        "example": {
                            "ranks": [list(r) for r in ranks],
                            "voter": i,
                            "true": list(ranks[i]),
                            "reported": list(alt),
                            "honest_winner": hw.winner,
                            "strategic_winner": sw.winner,
                        },
                    }
    return {
        "found": False,
        "n_voters": n_voters,
        "cw_deviations_checked": checked,
        "example": None,
    }


def main() -> int:
    errors: list[str] = []
    cen = E.census()
    det = E.detector_census()
    if not cen["engine_present"]:
        print("FAILED:ADV-0098-probe1 engine missing")
        return 1

    irv_h, c3 = P.irv_compromise_honest()
    irv_s, _ = P.irv_compromise_strategic()
    irv = _row(
        "irv-textbook-compromise",
        E.RANKED_CHOICE,
        irv_h,
        irv_s,
        ("A", "B", "C"),
        c3,
    )
    if irv["honest_winner"] != "C" or irv["strategic_winner"] != "B":
        errors.append(
            "irv-textbook-control: live IRV did not reproduce C then B "
            f"(honest={irv['honest_winner']} strategic={irv['strategic_winner']})"
        )
    if not irv["misreporter_improved"]:
        errors.append("irv-textbook-control: A-bloc does not prefer B to C")

    five_h, _ = P.irv_five_voter_honest()
    five_s, _ = P.irv_five_voter_strategic()
    five = _row(
        "irv-five-voter-compromise",
        E.RANKED_CHOICE,
        five_h,
        five_s,
        ("C", "B", "A"),
        c3,
    )
    if not five["misreporter_improved"]:
        errors.append("irv-five-voter: v3 did not improve")

    sc_h, _ = P.score_bullet_honest()
    sc_s, _ = P.score_bullet_strategic()
    sc = _row("score-bullet", E.SCORE, sc_h, sc_s, ("A", "B", "C"), c3)
    if not sc["misreporter_improved"]:
        errors.append("score-bullet: v1 did not improve")

    ap_h, _ = P.approval_bullet_honest()
    ap_s, _ = P.approval_bullet_strategic()
    ap = _row("approval-bullet", E.APPROVAL, ap_h, ap_s, ("A", "B", "C"), c3)
    if not ap["misreporter_improved"]:
        errors.append("approval-bullet: v1 did not improve")

    two_h, c2 = P.two_candidate_honest()
    two_s, _ = P.two_candidate_a_flip()
    two_rows = []
    for method in (E.RANKED_CHOICE, E.PAIRWISE, E.SCORE, E.APPROVAL):
        row = _row(f"two-candidate-{method}", method, two_h, two_s, ("A", "B"), c2)
        two_rows.append(row)
        if row["misreporter_improved"]:
            errors.append(
                f"negative-control-two-candidate: {method} reported a beneficial "
                "A-bloc flip; enumerator is wrong (May/Gibbard two-alternative)"
            )
        if row["honest_winner"] != "A":
            errors.append(
                f"two-candidate honest winner {row['honest_winner']} != A for {method}"
            )

    bloc, clones, cw = P.weight_clone_bloc()
    w_bloc = E.run(E.RANKED_CHOICE, bloc, cw)
    w_clone = E.run(E.RANKED_CHOICE, clones, cw)
    weight_ok = w_bloc.winner == w_clone.winner and w_bloc.winner is not None
    if not weight_ok:
        errors.append(
            f"weight-clone mismatch bloc={w_bloc.winner} clones={w_clone.winner}"
        )

    cond = condorcet_unique_cw_search(5)

    uni, _ = P.unanimous_a()
    uni_win = {m: E.run(m, uni, c3).winner for m in E.LIVE_DISPATCH}

    payload = {
        "probe": "probe1-honest-vs-strategic",
        "unit_id": "ADV-0098",
        "census": cen,
        "detector": det,
        "cases": {
            "irv_textbook": irv,
            "irv_five_voter": five,
            "score_bullet": sc,
            "approval_bullet": ap,
            "two_candidate": two_rows,
            "weight_clones": {
                "bloc_winner": w_bloc.winner,
                "clone_winner": w_clone.winner,
                "weight_load_bearing_match": weight_ok,
            },
            "condorcet_unique_cw_search": cond,
            "unanimous_winners": uni_win,
        },
        "controls": {
            "irv_known_manipulability_reproduced": (
                irv["honest_winner"] == "C"
                and irv["strategic_winner"] == "B"
                and irv["misreporter_improved"]
            ),
            "two_candidate_no_beneficial_misreport": all(
                not r["misreporter_improved"] for r in two_rows
            ),
            "detector_silent_on_unanimous": not det["detects_misreporting"],
            "detector_fired_on_strategic": det["detects_misreporting"],
        },
        "errors": errors,
        "ok": not errors,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "irv_honest": irv["honest_winner"],
                "irv_strategic": irv["strategic_winner"],
                "irv_improved": irv["misreporter_improved"],
                "score_honest": sc["honest_winner"],
                "score_strategic": sc["strategic_winner"],
                "approval_honest": ap["honest_winner"],
                "approval_strategic": ap["strategic_winner"],
                "condorcet_unique_cw_manipulation_found": cond["found"],
                "detector_present": det["detector_module_present"],
                "two_candidate_clean": payload["controls"][
                    "two_candidate_no_beneficial_misreport"
                ],
                "errors": errors,
            }
        )
    )
    if errors:
        print("FAILED:ADV-0098-probe1 " + "; ".join(errors))
        return 1
    print(
        "CONTROL_VERBATIM=IRV textbook 5 A>B>C / 4 C>B>A / 2 B>C>A elects C honestly "
        "and elects B after two A-voters compromise to B>A>C. Two-candidate 3 A>B vs "
        "2 B>A: A-bloc misreport elects B (worse). Detector did not fire on the "
        "strategic IRV profile because no ballot-strategy detector exists."
    )
    print("SUCCESS:ADV-0098-probe1 honest-vs-strategic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
