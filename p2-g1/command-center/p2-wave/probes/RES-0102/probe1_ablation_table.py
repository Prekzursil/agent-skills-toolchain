#!/usr/bin/env python3
"""RES-0102 delivery predicate: per-component ablation delta table.
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost
with the prior builder session; role follows the artifact (fail-closed)."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0102"

def recompute_row(row, base_acc):
    acc = row["n_correct"] / row["n_tasks"]
    delta = acc - base_acc
    return (abs(acc - float(row["accuracy"])) < 1e-9,
            abs(delta - float(row["delta_from_baseline"])) < 1e-9,
            abs(abs(delta) - float(row["abs_delta"])) < 1e-9,
            (abs(delta) < 0.05) == bool(row["approximately_zero"]),
            ("none-measured" if delta == 0 else ("helps" if delta > 0 else "hurts")) == row["effect"])

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    rows = doc.get("ablation_delta_table") or []
    full = next((r for r in rows if r.get("component") == "full"), None)
    c.append(("baseline 'full' row present", full is not None, f"n_rows={len(rows)}"))
    base_acc = float(full["accuracy"]) if full else 0.0
    comps = [r.get("component") for r in rows]
    needed = {"trigger_phrases", "negative_scope", "examples", "length_body"}
    c.append((">=4 components ablated besides the baseline", needed <= set(comps),
              f"components={comps}"))
    bad = []
    for r in rows:
        if r is full:
            continue
        res = recompute_row(r, base_acc)
        if not all(res):
            bad.append(r.get("component"))
    c.append(("every row recomputes: accuracy/delta/abs/zero-flag/effect", not bad,
              f"mismatched={bad}"))
    ctrl = [r for r in rows if r.get("is_control")]
    c.append(("exactly one irrelevant-component control, approximately zero",
              len(ctrl) == 1 and float(ctrl[0]["abs_delta"]) == 0.0,
              f"control={ctrl[0].get('component') if ctrl else None} "
              f"abs_delta={ctrl[0].get('abs_delta') if ctrl else None}"))
    gold = doc.get("gold_task_set") or {}
    c.append(("fixed gold task set declared with size and published-before flag",
              bool(gold.get("id")) and int(gold.get("n_tasks") or 0) == int((rows[0] or {}).get("n_tasks") or -1)
              and gold.get("published_before_measurement") is True,
              f"id={gold.get('id')} n={gold.get('n_tasks')}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
