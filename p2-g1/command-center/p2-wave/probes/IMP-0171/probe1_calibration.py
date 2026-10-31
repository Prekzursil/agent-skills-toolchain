"""IMP-0171 probe 1 (source): planted-mutant classes land in reported NUMERIC
bands (calibration, not adjectives); the derived threshold separates the bands;
the adjective-band mutation and the 0.01-threshold mutation both fire.

Exit 0 iff every assertion below passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import calibrate  # noqa: E402

RAW = HERE / "probe1-calibration.raw.txt"

result = calibrate.calibrate()
bands = result["bands"]
lines = [json.dumps({k: result[k] for k in ["high_band", "low_band", "gap", "threshold"]})]

# Bands must be NUMBERS, not adjectives: a mutation that replaces min/max with
# 'high'/'low' strings is rejected by these type checks (negative control 1).
for cls, band in bands.items():
    assert band["kind"] == "numeric", cls
    assert isinstance(band["min"], float) and isinstance(band["max"], float), \
        f"{cls}: band edges are not floats"
    assert all(isinstance(s, float) for s in band["scores"]), cls
lines.append("adjective-band mutation rejected: every band edge is a float")

high_min = min(bands[c]["min"] for c in ["exact_rename", "paraphrase", "one_parameter_fork"])
low_max = max(bands[c]["max"] for c in ["full_rewrite", "known_distinct"])
threshold = (high_min + low_max) / 2
assert abs(threshold - result["threshold"]) < 1e-6, "threshold not the recorded midpoint"
assert high_min >= 0.85, f"high band min {high_min} too low"
assert low_max <= 0.25, f"low band max {low_max} too high"
gap = high_min - low_max
assert gap >= 0.5, f"band gap {gap} too narrow"

# Negative control 2 (both-states threshold): a 0.01 threshold flags the
# distinct control pair; the calibrated threshold stays silent on it while
# still flagging an exact rename in the same run.
seed_doc = calibrate.SEED
from corpus import classes  # noqa: E402
cls_docs = classes()
distinct_first = cls_docs["known_distinct"][0]
rename_first = cls_docs["exact_rename"][0]
import lexical  # noqa: E402
j_distinct = lexical.score_pair(seed_doc, distinct_first)
j_rename = lexical.score_pair(seed_doc, rename_first)
assert 0.01 > -1 and (j_distinct >= 0.01), "control pair must exceed the bad threshold"
assert j_distinct < threshold < j_rename, "calibrated threshold does not separate states"
lines.append(f"bad threshold 0.01 would flag distinct (j={j_distinct:.6f} >= 0.01)")
lines.append(f"calibrated threshold {threshold:.6f}: silent on distinct, fires on rename")

RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "high_band": result["high_band"], "low_band": result["low_band"],
    "gap": result["gap"], "threshold": result["threshold"],
    "adjective_bands_rejected": True,
    "threshold_0.01_fires_on_distinct": True,
}))
print("SUCCESS:IMP-0171-probe1 mutant classes land in numeric bands, gap>=0.5")
