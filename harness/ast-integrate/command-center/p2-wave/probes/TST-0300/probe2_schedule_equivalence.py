#!/usr/bin/env python3
"""Probe 2: independent recount + round-robin/Swiss schedule equivalence.

Starts from the raw per-case scores (not from evaluate_field's summary).
Recomputes the pairwise margins with a nested loop and re-finds cycles
with a separate DFS. Then checks:

  * a transitive field: round-robin and Swiss agree on the top entry
  * an unstable field: they disagree, and the disagreement is a field
    finding — never resolved by picking a scheduler
  * format selector: small→round-robin, large→Swiss, tight budget→elimination

Reviewer mandate: statistics, independent of the author's ranking narrative.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from bench.tournament import (  # noqa: E402
    ELIMINATION,
    INSUFFICIENT_BUDGET,
    ROUND_ROBIN,
    SWISS,
    CaseScore,
    evaluate_field,
    mutant_pick_round_robin,
    schedule_unstable_scores,
    select_format,
    silently_resolves_schedule,
    transitive_scores,
    write_case_corpus,
)

OUT = HERE / "probe2-schedule-equivalence.raw.json"

# Independent expected Copeland-style pairwise winners on the unstable field.
UNSTABLE_WINNERS = {
    frozenset({"wf-apex", "wf-bold"}): "wf-apex",
    frozenset({"wf-cite", "wf-dash"}): "wf-cite",
    frozenset({"wf-cite", "wf-apex"}): "wf-cite",
    frozenset({"wf-bold", "wf-dash"}): "wf-bold",
    frozenset({"wf-apex", "wf-dash"}): "wf-apex",
    frozenset({"wf-bold", "wf-cite"}): "wf-bold",
}


def _fail(msg: str, payload: dict) -> int:
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=1))
    print(f"FAILED:TST-0300-probe2 {msg}")
    return 1


def independent_pairwise(scores: list[CaseScore]) -> dict[tuple[str, str], dict]:
    """Nested-loop recount. Does not call pairwise_matrix()."""
    by: dict[str, dict[str, float]] = defaultdict(dict)
    for row in scores:
        by[row.candidate_id][row.case_id] = float(row.score)
    cands = sorted(by)
    out: dict[tuple[str, str], dict] = {}
    for a, b in combinations(cands, 2):
        shared = sorted(set(by[a]) & set(by[b]))
        aw = bw = ties = 0
        for case_id in shared:
            sa, sb = by[a][case_id], by[b][case_id]
            if sa > sb:
                aw += 1
            elif sb > sa:
                bw += 1
            else:
                ties += 1
        n = len(shared)
        winner = a if aw > bw else b if bw > aw else None
        margin = 0.0 if n == 0 else (aw - bw) / n
        out[(a, b)] = {
            "a": a,
            "b": b,
            "a_wins": aw,
            "b_wins": bw,
            "ties": ties,
            "n_cases": n,
            "winner": winner,
            "margin": margin,
        }
    return out


def independent_cycles(cells: dict[tuple[str, str], dict]) -> list[list[str]]:
    """DFS cycle finder. Does not call enumerate_cycles()."""
    graph: dict[str, list[str]] = defaultdict(list)
    nodes: set[str] = set()
    for (a, b), cell in cells.items():
        nodes.add(a)
        nodes.add(b)
        if cell["winner"] == a:
            graph[a].append(b)
        elif cell["winner"] == b:
            graph[b].append(a)
    for n in nodes:
        graph.setdefault(n, [])
        graph[n] = sorted(set(graph[n]))

    def canon(path: list[str]) -> tuple[str, ...]:
        i = min(range(len(path)), key=lambda k: path[k])
        rot = path[i:] + path[:i]
        rev_body = list(reversed(path))
        j = min(range(len(path)), key=lambda k: rev_body[k])
        rev = rev_body[j:] + rev_body[:j]
        return tuple(rot if rot <= rev else rev)

    found: set[tuple[str, ...]] = set()

    def dfs(start: str, node: str, path: list[str], visiting: set[str]) -> None:
        for nxt in graph[node]:
            if nxt == start and len(path) >= 2:
                found.add(canon(path))
            elif nxt not in visiting:
                dfs(start, nxt, path + [nxt], visiting | {nxt})

    for s in sorted(nodes):
        dfs(s, s, [s], {s})
    return [list(c) for c in sorted(found, key=lambda t: (len(t), t))]


def main() -> int:
    errors: list[str] = []
    write_case_corpus()

    trans_scores = transitive_scores()
    trans_cells = independent_pairwise(trans_scores)
    trans_cycles = independent_cycles(trans_cells)
    if trans_cycles:
        errors.append(f"independent recount found cycles on transitive field {trans_cycles}")
    trans_winners = {cell["winner"] for cell in trans_cells.values()}
    if trans_winners != {"wf-apex", "wf-bold", "wf-cite"}:
        # dash never wins; apex beats all three, bold beats cite+dash, cite beats dash
        pass
    apex_wins = [
        cell
        for (a, b), cell in trans_cells.items()
        if "wf-apex" in (a, b) and cell["winner"] == "wf-apex"
    ]
    if len(apex_wins) != 3:
        errors.append(f"independent recount: apex should beat 3, beat {len(apex_wins)}")

    trans_report = evaluate_field(trans_scores)
    if trans_report.round_robin is None or trans_report.swiss is None:
        errors.append("transitive report missing scheduler results")
    else:
        if trans_report.round_robin.top != "wf-apex":
            errors.append(f"RR top {trans_report.round_robin.top!r}")
        if trans_report.swiss.top != "wf-apex":
            errors.append(f"Swiss top {trans_report.swiss.top!r}")
        if trans_report.schedule_agreement is not True:
            errors.append("transitive field must show schedule agreement")
        if trans_report.binding_top != "wf-apex":
            errors.append(f"binding_top {trans_report.binding_top!r}")
        if trans_report.schedule_finding is not None:
            errors.append("transitive field raised a schedule finding")

    unstable_scores = schedule_unstable_scores()
    unstable_cells = independent_pairwise(unstable_scores)
    for pair, want in UNSTABLE_WINNERS.items():
        a, b = sorted(pair)
        cell = unstable_cells.get((a, b))
        if cell is None or cell["winner"] != want:
            errors.append(f"independent {a} vs {b}: {cell} want winner={want}")

    # Reproduce effect size: each dedicated pair-case is a 1-0, margin ±1.0.
    for (a, b), cell in unstable_cells.items():
        if cell["n_cases"] != 1 or abs(cell["margin"]) != 1.0:
            errors.append(f"unstable margin {a}|{b} {cell}")

    unstable_cycles = independent_cycles(unstable_cells)
    cycle_members = {m for cyc in unstable_cycles for m in cyc}
    if {"wf-apex", "wf-bold", "wf-cite"} - cycle_members:
        errors.append(f"independent DFS missed the 3-cycle: {unstable_cycles}")

    unstable_report = evaluate_field(unstable_scores)
    if unstable_report.schedule_agreement is not False:
        errors.append("unstable field must disagree across schedulers")
    if unstable_report.swiss is None or unstable_report.swiss.top != "wf-cite":
        errors.append(
            f"Swiss top {None if unstable_report.swiss is None else unstable_report.swiss.top!r}"
        )
    if unstable_report.round_robin is None or unstable_report.round_robin.top is not None:
        errors.append(
            "round-robin must refuse a unique top on the Copeland 3-tie"
        )
    if unstable_report.binding_top is not None:
        errors.append(
            f"binding_top={unstable_report.binding_top} picked a scheduler on a disagreement"
        )
    if not unstable_report.schedule_finding:
        errors.append("unstable field produced no schedule finding")
    if silently_resolves_schedule(unstable_report):
        errors.append("live unstable report trips silently_resolves_schedule")
    mutant = mutant_pick_round_robin(unstable_report)
    if not silently_resolves_schedule(mutant):
        errors.append("mutant RR-pick did not fire silently_resolves_schedule")

    # Match library margins against the independent recount (effect size).
    for key, cell in unstable_report.matrix.items():
        a, b = key.split("|")
        indie = unstable_cells[(a, b)]
        if indie["winner"] != cell.winner:
            errors.append(f"margin winner drift {key}: lib={cell.winner} indie={indie['winner']}")
        if not math.isclose(indie["margin"], cell.margin, abs_tol=1e-12):
            errors.append(f"effect-size drift {key}: lib={cell.margin} indie={indie['margin']}")

    formats = {
        "small": select_format(4),
        "large": select_format(16),
        "tight": select_format(6, 5),
        "too-tight": select_format(6, 4),
    }
    if formats["small"] != ROUND_ROBIN:
        errors.append(f"small field format {formats['small']!r}")
    if formats["large"] != SWISS:
        errors.append(f"large field format {formats['large']!r} (must not silently RR)")
    if formats["tight"] != ELIMINATION:
        errors.append(f"budget-forced format {formats['tight']!r}")
    if formats["too-tight"] != INSUFFICIENT_BUDGET:
        errors.append(f"under-budget format {formats['too-tight']!r}")

    payload = {
        "pass": not errors,
        "errors": errors,
        "transitive": {
            "independent_cycles": trans_cycles,
            "apex_pairwise_wins": len(apex_wins),
            "rr_top": None if trans_report.round_robin is None else trans_report.round_robin.top,
            "swiss_top": None if trans_report.swiss is None else trans_report.swiss.top,
            "agreement": trans_report.schedule_agreement,
        },
        "unstable": {
            "independent_cycles": unstable_cycles,
            "independent_winners": {
                f"{a}|{b}": c["winner"] for (a, b), c in unstable_cells.items()
            },
            "rr_top": None
            if unstable_report.round_robin is None
            else unstable_report.round_robin.top,
            "rr_tied": None
            if unstable_report.round_robin is None
            else unstable_report.round_robin.tied_tops,
            "swiss_top": None if unstable_report.swiss is None else unstable_report.swiss.top,
            "agreement": unstable_report.schedule_agreement,
            "finding_kind": (unstable_report.schedule_finding or {}).get("kind"),
            "binding_top": unstable_report.binding_top,
            "mutant_fired": silently_resolves_schedule(mutant),
            "live_silent": not silently_resolves_schedule(unstable_report),
        },
        "format_selector": formats,
    }
    if errors:
        return _fail("; ".join(errors), payload)
    OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=1))
    print(
        f"transitive agree top=wf-apex; unstable finding="
        f"{(unstable_report.schedule_finding or {}).get('kind')} "
        f"swiss={None if unstable_report.swiss is None else unstable_report.swiss.top}"
    )
    print("SUCCESS:TST-0300-probe2 independent recount; schedule equivalence / field finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
