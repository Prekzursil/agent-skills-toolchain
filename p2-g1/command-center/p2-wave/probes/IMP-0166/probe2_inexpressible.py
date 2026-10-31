"""IMP-0166 probe 2 (verifier, both-states control): the inexpressible prose rule
"cand-inexpressible-feels-done" classifies UNKNOWN-NEEDS-PROBE, asserted BY ID,
while its expressible twin classifies EVALUABLE; a planted approximator that
snaps prose onto completeness_score diverges from the production extractor.

Exit 0 iff the classification map matches and the approximator diverges.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from candidates import candidate_set  # noqa: E402
from extract import extract_all, planted_approximator  # noqa: E402
import algebra  # noqa: E402

RAW = HERE / "probe2-inexpressible.raw.txt"

rows = extract_all(candidate_set())
classifications = {r["id"]: r["classification"] for r in rows}
lines = [json.dumps({"probe": "probe2-inexpressible", "classifications": classifications}, indent=1)]

bad_id = "cand-inexpressible-feels-done"
good_id = "cand-expressible-twin-10937"
bad = classifications[bad_id]
good = classifications[good_id]
assert bad == "UNKNOWN-NEEDS-PROBE", f"{bad_id} -> {bad}, not flagged"
assert good == "EVALUABLE", f"{good_id} -> {good}, twin must parse"
# The second inexpressible prose rule and the empty rule are also honest.
assert classifications["cand-inexpressible-juice"] == "UNKNOWN-NEEDS-PROBE"
assert classifications["cand-none"] == "NONE"
# Every spec-named expression stays EVALUABLE.
for i in range(10937, 10943):
    assert classifications[f"cand-spec-{i}"] == "EVALUABLE", f"cand-spec-{i} regressed"

# Approximator mutation: snaps the inexpressible prose onto a real metric.
approx_tree = planted_approximator("stop when it feels done")
approx_verdict = algebra.evaluate(approx_tree, {"completeness_score": 0.99})
production = classifications[bad_id]
diverged = (approx_verdict in ("TRUE", "FALSE")) and production == "UNKNOWN-NEEDS-PROBE"
assert diverged, "planted approximator did not diverge from the production extractor"

lines.append(f"bad_id={bad_id} classification={bad} good_id={good_id} "
             f"classification={good} approximator_diverged=yes")
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({
    "unknown_ids": [k for k, v in classifications.items() if v == "UNKNOWN-NEEDS-PROBE"],
    "asserted": bad_id,
    "approximator_diverged": "yes",
}))
print("SUCCESS:IMP-0166-probe2 inexpressible flagged, never approximated")
