#!/usr/bin/env python
"""Turn the one actionable recommendation into a MEASURED number instead of an opinion.

`WAVE4-CEILING-PROBE.json` refuted half my mechanism hypothesis (saturation does NOT
separate) and confirmed the other half: the negatives that false-fire are the ones whose
vocabulary the corpus largely does not know. The candidate out-of-domain signal is
therefore `frac_tokens_known` - the fraction of a query's content tokens that exist in the
corpus vocabulary at all - which the router currently does not use.

This sweeps that one signal as a gate IN FRONT of the existing AND-gate and reports the
exact trade at each cut: how many false fires it would suppress vs how many true positives
it would destroy. A recommendation without this table is a guess.

CONTROL: the cut must be non-trivial at both ends - cut=0.0 suppresses nothing (identical
to today) and cut>max suppresses everything. A sweep that does not span those is not
applying the gate.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "WAVE4-CEILING-PROBE.json"
OUT = HERE / "WAVE4-OOD-SEPARATION.json"

d = json.loads(SRC.read_text(encoding="utf-8"))
neg = d["rows"]["negatives"]
pos_sample = d["rows"]["positives"]  # first 20 positives were retained in the artifact

neg_fire = [r for r in neg if r["fits"]]
pos_fire = [r for r in pos_sample if r["fits"]]

rows = []
for cut in (0.0, 0.55, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 1.0, 1.01):
    suppressed_neg = [r for r in neg_fire if r["frac_tokens_known"] < cut]
    suppressed_pos = [r for r in pos_fire if r["frac_tokens_known"] < cut]
    rows.append(
        {
            "frac_known_cut": cut,
            "false_fires_suppressed": len(suppressed_neg),
            "of_false_fires": len(neg_fire),
            "false_fire_suppression_rate": round(len(suppressed_neg) / len(neg_fire), 4)
            if neg_fire
            else None,
            "TRUE_POSITIVES_LOST": len(suppressed_pos),
            "of_positives_measured": len(pos_fire),
            "true_positive_loss_rate": round(len(suppressed_pos) / len(pos_fire), 4)
            if pos_fire
            else None,
        }
    )

best = max(
    (r for r in rows if (r["TRUE_POSITIVES_LOST"] or 0) == 0),
    key=lambda r: r["false_fires_suppressed"],
    default=None,
)

out = {
    "unit": "close/audit-probe-repair (out-of-domain gate, measured trade)",
    "signal": "frac_tokens_known = |query content tokens present in SemanticModel.idf| / "
    "|query content tokens|",
    "why_this_one": "WAVE4-CEILING-PROBE measured median frac_known 0.500 on the 24 "
    "negatives that false-fire vs 1.000 on the 54 labelled positives; the saturation arm "
    "of the same hypothesis was REFUTED (0.880 firing-negative vs 1.021 positive), so "
    "this is the arm that survived, not the arm I guessed first",
    "population_note": "positives here are the 20 retained in the ceiling artifact, NOT "
    "all 54 - so the true-positive loss column is a 20-query estimate and its confidence "
    "band is correspondingly wide. Settling experiment: rerun over all 54 + the 22 "
    "authored positives before wiring any gate.",
    "sweep": rows,
    "largest_cut_with_zero_measured_true_positive_loss": best,
    "control": {
        "cut=0.0_suppresses_nothing": rows[0]["false_fires_suppressed"] == 0
        and rows[0]["TRUE_POSITIVES_LOST"] == 0,
        "cut=1.01_suppresses_everything": rows[-1]["false_fires_suppressed"]
        == len(neg_fire)
        and rows[-1]["TRUE_POSITIVES_LOST"] == len(pos_fire),
        "spans_both_ends": (
            rows[0]["false_fires_suppressed"] == 0
            and rows[-1]["false_fires_suppressed"] == len(neg_fire)
        ),
    },
    "NOT_A_RECOMMENDATION_TO_SHIP": "this is a measured trade, not a merged change. It "
    "belongs to the routing lane, not to an audit probe, and it needs the full-population "
    "rerun above plus a regression pass before anyone changes router.py.",
}
OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
print("SUCCESS:wave4-ood-separation")
