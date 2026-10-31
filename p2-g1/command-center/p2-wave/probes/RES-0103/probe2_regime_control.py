#!/usr/bin/env python3
"""RES-0103 independent re-derivation: symbolic regime sweep + NC mutant.
Sweeps the Bayes-reject cost model over a p grid for both ratios."""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0103"

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    th = doc.get("threshold_recommendation") or {}
    mw, mm = float(th["assumed_cost_wrong"]), float(th["assumed_cost_miss"])
    tau = 1 - mm / mw
    # sweep: answer cost (1-p)*C_wrong vs abstain cost C_miss
    worse_any = any((1 - pv) * mw < mm for pv in [i / 100 for i in range(101)])
    abstain_wins_at = [pv for pv in [i / 100 for i in range(101)] if mm <= (1 - pv) * mw]
    c.append(("primary ratio: abstention strictly cheaper below tau and never above",
              worse_any and all(pv <= tau + 1e-9 for pv in abstain_wins_at),
              f"tau={tau:.2f} abstain-wins-p-max={max(abstain_wins_at)}"))
    iw, im = float(th["inverted_cost_wrong"]), float(th["inverted_cost_miss"])
    inv_abstain_wins = [pv for pv in [i / 100 for i in range(101)] if im <= (1 - pv) * iw]
    c.append(("inverted ratio: abstention strictly worse at every confidence",
              not inv_abstain_wins,
              f"inverted tau={max(0.0, 1 - im / iw):.2f} abstain-wins-anywhere={bool(inv_abstain_wins)}"))

    def mutate(d):
        d["threshold_recommendation"]["assumed_cost_wrong"] = 2.0  # ratio corrupted 4:1 -> 2:1
        return d

    mp = L.mutation_copy(doc, mutate)
    try:
        mdoc = json.loads(mp.read_text(encoding="utf-8"))
        t2 = mdoc["threshold_recommendation"]
        recomputed = 1 - float(t2["assumed_cost_miss"]) / float(t2["assumed_cost_wrong"])
        fired = abs(recomputed - float(t2["tau"])) > 1e-9
        c.append(("NC: corrupted ratio no longer matches the recorded tau", fired,
                  f"mutant recomputed tau={recomputed} recorded={t2['tau']}"))
    finally:
        mp.unlink(missing_ok=True)
    return L.finish(UID, "probe2", c)

if __name__ == "__main__":
    raise SystemExit(main())
