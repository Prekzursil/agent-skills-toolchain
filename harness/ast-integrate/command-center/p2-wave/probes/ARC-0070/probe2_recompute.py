#!/usr/bin/env python3
"""Probe 2: independent recomputation from the published pairwise matrix,
plus the sensitivity (drop most-influential judge) control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import aggregate as A  # noqa: E402
import fixtures as F  # noqa: E402
import recompute as R  # noqa: E402

ART = REPO / "command-center/phase3/AGGREGATE-RANKING.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0070-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("AGGREGATE-RANKING.json missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(doc)
    if doc.get("unit_id") != "ARC-0070":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:ARC-0070" not in blob:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("kind") != "aggregate-ranking":
        return fail(f"kind {doc.get('kind')}")

    pairs = doc.get("pairwise_matrix") or []
    ranking = doc.get("ranking") or []
    entries = [r["entry_id"] for r in ranking if isinstance(r, dict) and r.get("entry_id")]
    if len(entries) < 2:
        return fail("ranking too short")
    published_order = entries
    ev = {}
    for row in ranking:
        if isinstance(row, dict) and row.get("entry_id"):
            ev[str(row["entry_id"])] = float(row.get("evidence_weighted_total") or 0.0)
    # Prefer the published totals map when present (matrix-only recompute still
    # uses Copeland/Schulze first; totals only split remaining ties).
    if isinstance(doc.get("evidence_weighted_totals"), dict):
        ev.update({str(k): float(v) for k, v in doc["evidence_weighted_totals"].items()})

    ind = R.rank_from_matrix(pairs, entries, ev)
    print(
        json.dumps(
            {
                "published_order": published_order,
                "recomputed_order": ind["ranking"],
                "published_condorcet": doc.get("condorcet_winner"),
                "recomputed_condorcet": ind["condorcet_winner"],
                "published_cycles": [c.get("members") for c in (doc.get("cycles") or [])],
                "recomputed_cycles": ind["cycles"],
            },
            sort_keys=True,
        )
    )
    if ind["ranking"] != published_order:
        return fail(
            f"ranking mismatch published={published_order} recomputed={ind['ranking']}"
        )
    if ind["condorcet_winner"] != doc.get("condorcet_winner"):
        return fail("condorcet_winner mismatch")
    pub_cycles = [tuple(c.get("members") or []) for c in (doc.get("cycles") or [])]
    rec_cycles = [tuple(c) for c in ind["cycles"]]
    if pub_cycles != rec_cycles:
        return fail(f"cycles mismatch {pub_cycles} vs {rec_cycles}")

    # Fresh aggregation from the same input snapshot must match the matrix.
    snap = doc.get("input_snapshot") or {}
    scorecards = snap.get("scorecards")
    rubric = snap.get("rubric")
    if not isinstance(scorecards, dict) or not isinstance(rubric, dict):
        return fail("input_snapshot missing; cannot re-aggregate from raw cards")
    fresh = A.aggregate(scorecards, rubric, REPO)
    fresh_order = [r["entry_id"] for r in fresh["ranking"]]
    if fresh_order != published_order:
        return fail(f"raw re-aggregate {fresh_order} != published {published_order}")

    # Sensitivity: drop the most influential judge; winner-change flag must match.
    sens = A.sensitivity(scorecards, rubric, REPO)
    published_s = doc.get("sensitivity") or {}
    print(
        json.dumps(
            {
                "sensitivity_most_influential": sens["most_influential_judge"],
                "sensitivity_winner_changed": sens["winner_changed"],
                "sensitivity_baseline_winner": sens["baseline_winner"],
                "sensitivity_dropped_winner": sens["dropped_winner"],
                "published_most_influential": published_s.get("most_influential_judge"),
                "published_winner_changed": published_s.get("winner_changed"),
            },
            sort_keys=True,
        )
    )
    if sens["most_influential_judge"] != published_s.get("most_influential_judge"):
        return fail("most_influential_judge mismatch")
    if bool(sens["winner_changed"]) != bool(published_s.get("winner_changed")):
        return fail("winner_changed mismatch")
    if sens["baseline_winner"] != published_s.get("baseline_winner"):
        return fail("baseline_winner mismatch")
    if sens["dropped_winner"] != published_s.get("dropped_winner"):
        return fail("dropped_winner mismatch")

    tb = doc.get("tie_break") or {}
    if tb.get("cycle_silently_broken") is not False:
        return fail("tie_break.cycle_silently_broken must be false")
    does_not = doc.get("does_not_mean") or []
    if len(does_not) < 4:
        return fail("does_not_mean too short")
    print("SUCCESS:ARC-0070-probe2 recomputation and sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
