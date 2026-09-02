#!/usr/bin/env python3
"""Probe 1: size-sweep + independent recount of the crossover n.

Author path: crossover_forward over simulated rows.
Reviewer path: crossover_by_min rebuilding recovered sets, then min() of wins.
Disagreement on the number blocks the unit.
The design-note claimed crossover_n must match both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sim as S  # noqa: E402

NOTE = REPO / "command-center/design/council/CNL-0030-chair-led-topology-and-agenda-control.md"


def main() -> int:
    params = S.load_params()
    rows = S.sweep(params)
    author = S.crossover_forward(rows)
    reviewer = S.crossover_by_min(params)
    if not NOTE.is_file():
        print("FAILED:CNL-0030-probe1 design note missing")
        return 1
    doc = json.loads(NOTE.read_text(encoding="utf-8"))
    claimed = doc.get("size_sweep", {}).get("crossover_n")
    rec_claimed = doc.get("reviewer", {}).get("recounted_crossover_n")
    print(
        f"metric={params['metric_name']} budget={params['read_budget_tokens']} "
        f"flat_stmt={params['flat_statement_tokens']} nom={params['nomination_tokens']} "
        f"slot={params['chair_slot_tokens']}"
    )
    for row in rows:
        print(
            f"n={row['n']} flat={row['flat_recovery']} chair={row['chair_recovery']} "
            f"beats={row['chair_beats_flat']} flat_msg={row['flat_messages']} "
            f"chair_msg={row['chair_messages']} lb={row['load_bearing_seats']} "
            f"flat_lb={row['flat_lb_recovered']} chair_lb={row['chair_lb_recovered']}"
        )
    print(
        f"author_crossover={author} reviewer_crossover={reviewer} "
        f"note_crossover={claimed} note_reviewer={rec_claimed}"
    )
    note_rows = doc.get("size_sweep", {}).get("rows") or []
    by_n = {int(r["n"]): r for r in note_rows if isinstance(r, dict) and "n" in r}
    drift = False
    for row in rows:
        rec = by_n.get(int(row["n"]))
        if rec is None:
            print(f"FAILED:CNL-0030-probe1 missing note row n={row['n']}")
            drift = True
            continue
        for key in (
            "flat_recovery",
            "chair_recovery",
            "chair_beats_flat",
            "flat_messages",
            "chair_messages",
        ):
            if rec.get(key) != row.get(key):
                print(
                    f"FAILED:CNL-0030-probe1 row drift n={row['n']} {key} "
                    f"note={rec.get(key)} live={row.get(key)}"
                )
                drift = True
    if author is None or reviewer is None or author != reviewer:
        print("FAILED:CNL-0030-probe1 independent recount disagreement")
        return 1
    if claimed != author or rec_claimed != reviewer:
        print("FAILED:CNL-0030-probe1 design-note crossover mismatch")
        return 1
    if drift:
        return 1
    if "SUCCESS:CNL-0030" not in NOTE.read_text(encoding="utf-8"):
        print("FAILED:CNL-0030-probe1 sentinel-absent")
        return 1
    print(f"crossover_n={author}")
    print("SUCCESS:CNL-0030-probe1 size-sweep crossover and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
