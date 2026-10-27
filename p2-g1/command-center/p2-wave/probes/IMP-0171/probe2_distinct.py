"""IMP-0171 probe 2 (verifier, false-positive control): the named known-distinct
pair scores in the LOW band, below the calibrated threshold; a full rewrite of
the seed lands in the same low band - recorded honestly as this instrument's
lexical blind spot, not tuned away.

Exit 0 iff both controls hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lexical  # noqa: E402
from corpus import SEED, DISTINCT_NAMES, classes  # noqa: E402
import calibrate  # noqa: E402

RAW = HERE / "probe2-distinct.raw.txt"

cal = calibrate.calibrate()
threshold = cal["threshold"]
low_max = cal["low_band"][1]

first = classes()["known_distinct"][0]
j = lexical.jaccard(SEED, first)
pair = ["seed-harbor-review-gate", DISTINCT_NAMES[0]]
lines = [json.dumps({"pair": pair, "intersection": j["intersection"],
                     "union": j["union"], "jaccard": round(j["jaccard"], 6),
                     "threshold": threshold, "low_band_max": low_max})]
assert j["jaccard"] <= low_max + 1e-9, "distinct pair left the low band"
assert j["jaccard"] < threshold, "distinct pair crosses the lexical threshold"

rewrite = classes()["full_rewrite"][0]
jrw = lexical.score_pair(SEED, rewrite)
lines.append(f"full_rewrite of the seed scores {jrw:.6f}, same low band "
             f"(lexical instrument cannot detect a full rewrite)")
assert jrw <= low_max + 1e-9, "full rewrite unexpectedly separable lexically"

# Rename in the same run still fires: the detector is not simply failing all.
rename = classes()["exact_rename"][0]
jrn = lexical.score_pair(SEED, rename)
assert jrn > threshold, "rename control did not fire"
lines.append(f"rename control scores {jrn:.6f} > threshold, fires")
lines.append("PASS: known-distinct control scores low, rename fires, "
             "full rewrite honestly inside the blind spot")
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "pair": pair, "intersection": j["intersection"], "union": j["union"],
    "jaccard": round(j["jaccard"], 6), "in_low_band": True,
    "full_rewrite_jaccard": round(jrw, 6), "rename_fires": True,
}))
print("SUCCESS:IMP-0171-probe2 known-distinct control scores in the low band")
