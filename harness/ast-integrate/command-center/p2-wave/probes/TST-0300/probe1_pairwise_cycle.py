#!/usr/bin/env python3
"""Probe 1: pairwise matrix + planted-cycle control.

Loads the three-candidate non-transitive fixture, checks that the published
matrix matches a hand count, and that the cycle is named rather than
collapsed into a leaderboard. Both-states: a mutant that binds a Copeland
order must make hides_nontransitivity() fire; the live report must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.tournament import (  # noqa: E402
    PARTIAL_ORDER,
    TOTAL_ORDER,
    evaluate_field,
    hides_nontransitivity,
    mutant_hide_cycle,
    planted_cycle_scores,
    scores_from_fixture_doc,
    transitive_scores,
    write_case_corpus,
)

OUT = HERE / "probe1-pairwise-cycle.raw.json"

# Hand count of the three matched cases (not copied from evaluate_field).
# case-1: a=3,b=2,c=1; case-2: a=1,b=3,c=2; case-3: a=2,b=1,c=3.
HAND = {
    "wf-cycle-a|wf-cycle-b": {"winner": "wf-cycle-a", "a_wins": 2, "b_wins": 1},
    "wf-cycle-a|wf-cycle-c": {"winner": "wf-cycle-c", "a_wins": 1, "b_wins": 2},
    "wf-cycle-b|wf-cycle-c": {"winner": "wf-cycle-b", "a_wins": 2, "b_wins": 1},
}


def _fail(msg: str, payload: dict) -> int:
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=1))
    print(f"FAILED:TST-0300-probe1 {msg}")
    return 1


def main() -> int:
    errors: list[str] = []
    written = write_case_corpus()
    disk = REPO / "command-center" / "bench" / "cases" / "tst-0300-planted-cycle.json"
    if not disk.is_file():
        return _fail("planted-cycle corpus missing", {"errors": ["corpus-missing"]})
    doc = json.loads(disk.read_text(encoding="utf-8"))
    from_disk = scores_from_fixture_doc(doc)
    live = planted_cycle_scores()
    if [(s.candidate_id, s.case_id, s.score) for s in from_disk] != [
        (s.candidate_id, s.case_id, s.score) for s in live
    ]:
        errors.append("disk corpus drifted from planted_cycle_scores()")

    report = evaluate_field(live)
    matrix = {k: v.to_dict() for k, v in report.matrix.items()}
    for key, want in HAND.items():
        cell = matrix.get(key) or {}
        if (
            cell.get("winner") != want["winner"]
            or cell.get("a_wins") != want["a_wins"]
            or cell.get("b_wins") != want["b_wins"]
            or cell.get("n_cases") != 3
        ):
            errors.append(f"matrix {key} {cell} != {want}")

    members = {m for cyc in report.cycles for m in cyc}
    want_members = {"wf-cycle-a", "wf-cycle-b", "wf-cycle-c"}
    if want_members != members:
        errors.append(f"cycle members {members} != {want_members}")
    if not any(set(cyc) == want_members for cyc in report.cycles):
        errors.append(f"no 3-cycle covering the planted field: {report.cycles}")
    if report.ranking_kind != PARTIAL_ORDER:
        errors.append(f"ranking_kind={report.ranking_kind} (cycle must not be a total order)")
    if report.binding_leaderboard is not None:
        errors.append("binding_leaderboard set on a cyclic field")
    if report.binding_top is not None:
        errors.append(f"binding_top={report.binding_top} hides the cycle")
    if hides_nontransitivity(report):
        errors.append("live report trips hides_nontransitivity")
    mutant = mutant_hide_cycle(report)
    if not hides_nontransitivity(mutant):
        errors.append("mutant Copeland collapse did not fire hides_nontransitivity")
    if mutant.ranking_kind != TOTAL_ORDER or mutant.binding_top is None:
        errors.append("mutant did not bind a fake total order")

    trans = evaluate_field(transitive_scores())
    if trans.cycles:
        errors.append(f"transitive control has cycles {trans.cycles}")
    if trans.ranking_kind != TOTAL_ORDER:
        errors.append(f"transitive ranking_kind={trans.ranking_kind}")
    if trans.binding_top != "wf-apex":
        errors.append(f"transitive top {trans.binding_top!r}")
    if hides_nontransitivity(trans):
        errors.append("transitive control tripped the cycle detector")

    payload = {
        "pass": not errors,
        "errors": errors,
        "corpus_written": written,
        "pairwise_matrix": matrix,
        "cycles": report.cycles,
        "ranking_kind": report.ranking_kind,
        "owner_action": report.owner_action,
        "mutant_fired": hides_nontransitivity(mutant),
        "live_silent": not hides_nontransitivity(report),
        "transitive_top": trans.binding_top,
    }
    if errors:
        return _fail("; ".join(errors), payload)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=1))
    print(
        "planted cycle members="
        + ",".join(sorted(members))
        + f" kind={report.ranking_kind} matrix_cells={len(matrix)}"
    )
    print("SUCCESS:TST-0300-probe1 pairwise matrix computed; planted cycle named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
