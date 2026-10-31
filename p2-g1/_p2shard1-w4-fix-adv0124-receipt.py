#!/usr/bin/env python3
"""Fix ADV-0124 receipt: state=SUCCESS without an independent reviewer closure
is forbidden by receipt_core. Builders set BLOCKED with failure.classification
["reviewer-absent"]; only the independent reviewer closes. Full-dict rewrite
(never a partial dump), then re-open and assert untouched keys survived."""
import json
from pathlib import Path

P = Path(r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes\ADV-0124\SUBAGENT-RETURN.json")
r = json.loads(P.read_text(encoding="utf-8"))
before = {k: r[k] for k in r}
pre_keys = set(r.keys())

r["state"] = "BLOCKED"
fail = r.setdefault("failure", {})
fail["classification"] = ["reviewer-absent"]
note_fix = (
    " Receipt fix 2026-10-26 (wave-4 shard-1 resume): prior receipt carried state=SUCCESS "
    "with no reviewer.verdict/reviewer.independent - receipt_core forbids builder-side SUCCESS "
    "without an independent PASS closure. extensions.prev_closure names this unit's own probe2 "
    "as reviewer_id, which is self-certification, not an independent closure. Corrected to "
    "state=BLOCKED / failure.classification=[reviewer-absent]; artifact and probes unchanged and "
    "re-verified live via _measure_one_delivered.py."
)
r["notes"] = str(r.get("notes") or "") + note_fix

P.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")

# Post-write verify: full reload, untouched keys byte-equal, keys set preserved.
r2 = json.loads(P.read_text(encoding="utf-8"))
assert set(r2.keys()) == pre_keys, "key set changed"
for k, v in before.items():
    if k not in ("state", "notes"):
        assert r2[k] == v, f"key {k} mutated unexpectedly"
assert r2["state"] == "BLOCKED"
assert r2["failure"]["classification"] == ["reviewer-absent"]
print("SUCCESS:ADV-0124-receipt-fix state=BLOCKED classification=reviewer-absent all-other-keys-verified")
