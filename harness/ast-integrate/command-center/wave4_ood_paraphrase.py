#!/usr/bin/env python
"""CORRECTING MY OWN OVERCLAIM before anyone can cite it.

`WAVE4-OOD-SEPARATION.json` reported that a `frac_tokens_known >= 0.85` pre-gate would
suppress 24/24 false fires at ZERO measured true-positive cost. That number is inflated by
the population it was measured on: the 20 positives retained in the ceiling artifact are
the FIRST 20 of the labelled set, which is the L1 tier - queries MECHANICALLY DERIVED from
the capability's own text. Their vocabulary is corpus vocabulary by construction, so
frac_known ~ 1.0 is guaranteed and a vocabulary gate cannot possibly cost anything there.

The population that matters is the PARAPHRASE tiers, where a person uses their own words:
the lane's L2 (21) and L4 (5), plus the 22 authored QS-C positives. This file measures the
same gate on those, so the recommendation stands or falls on the honest population.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "platform"
OUT = HERE / "WAVE4-OOD-PARAPHRASE.json"
sys.path.insert(0, str(BUILD))

from routing import index as ridx  # noqa: E402
from routing import queries as rq  # noqa: E402
from routing.descriptions import tokens  # noqa: E402
from routing.router import Router  # noqa: E402

import importlib.util  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


ab = _load("w4ab", HERE / "wave4_abstain_probe.py")
pr = _load("w4pr", HERE / "wave4_routing_probe.py")

raw = ridx.discover()
router = Router.build(raw)
qs = rq.build(ridx.discover())
known_ids = set(raw.by_id())


def frac_known(text: str) -> float:
    toks = tokens(text)
    if not toks:
        return 0.0
    return round(sum(1 for t in toks if t in router.model.idf) / len(toks), 4)


groups: dict[str, list[dict]] = {"L1": [], "L2": [], "L4": [], "QS-C-authored": []}
for q in qs.queries:
    if not q.gold:
        continue
    if q.tier in groups:
        groups[q.tier].append({"qid": q.qid, "text": q.text, "gold": sorted(q.gold)})
for text, gold in pr.QS_C:
    g = [x for x in gold if x in known_ids]
    if g:
        groups["QS-C-authored"].append({"qid": "C", "text": text, "gold": g})

for name, rows in groups.items():
    for r in rows:
        d = router.route(r["text"], k=5)
        r["frac_known"] = frac_known(r["text"])
        r["fits"] = d.fits
        r["gold_hit"] = bool(set(d.ids) & set(r["gold"]))

neg_fire = []
for t in ab.LANE_NEGATIVES + ab.MY_NEGATIVES:
    d = router.route(t, k=5)
    if d.fits:
        neg_fire.append({"text": t, "frac_known": frac_known(t)})

paraphrase = groups["L2"] + groups["L4"] + groups["QS-C-authored"]
sweep = []
for cut in (0.0, 0.55, 0.70, 0.80, 0.85, 0.90, 1.0):
    ff = [r for r in neg_fire if r["frac_known"] < cut]
    # a true positive is LOST only if the router was actually getting it right today
    winners = [r for r in paraphrase if r["gold_hit"]]
    lost = [r for r in winners if r["frac_known"] < cut]
    l1_winners = [r for r in groups["L1"] if r["gold_hit"]]
    l1_lost = [r for r in l1_winners if r["frac_known"] < cut]
    sweep.append(
        {
            "frac_known_cut": cut,
            "false_fires_suppressed": f"{len(ff)}/{len(neg_fire)}",
            "false_fire_suppression_rate": round(len(ff) / len(neg_fire), 4)
            if neg_fire
            else None,
            "PARAPHRASE_correct_hits_LOST": f"{len(lost)}/{len(winners)}",
            "paraphrase_loss_rate": round(len(lost) / len(winners), 4)
            if winners
            else None,
            "L1_correct_hits_lost": f"{len(l1_lost)}/{len(l1_winners)}",
        }
    )

med = {
    name: (
        round(statistics.median([r["frac_known"] for r in rows]), 4) if rows else None
    )
    for name, rows in groups.items()
}
med["negatives_that_FIRE"] = (
    round(statistics.median([r["frac_known"] for r in neg_fire]), 4)
    if neg_fire
    else None
)

out = {
    "unit": "close/audit-probe-repair (OOD gate on the HONEST population)",
    "correction": "WAVE4-OOD-SEPARATION.json measured true-positive cost on 20 L1 queries, "
    "whose vocabulary is corpus vocabulary BY CONSTRUCTION (mechanically derived from the "
    "record's own text). Its zero-loss column was therefore uninformative about real user "
    "phrasing. This file re-measures on L2 + L4 + the 22 authored QS-C positives.",
    "median_frac_known_by_population": med,
    "counts": {k: len(v) for k, v in groups.items()},
    "n_false_firing_negatives": len(neg_fire),
    "sweep_on_paraphrase_population": sweep,
    "rows": {"paraphrase": paraphrase, "negatives_that_fire": neg_fire},
}
zero = [
    s
    for s in sweep
    if s["paraphrase_loss_rate"] == 0.0 and (s["false_fire_suppression_rate"] or 0) > 0
]
out["verdict"] = {
    "a_cut_exists_that_suppresses_false_fires_at_zero_paraphrase_cost": bool(zero),
    "best_zero_cost_cut": zero[-1] if zero else None,
    "honest_reading": (
        "the gate is worth the routing lane's time"
        if zero
        else "the vocabulary gate trades real recall for abstention and is NOT free"
    ),
}
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))
print("SUCCESS:wave4-ood-paraphrase")
