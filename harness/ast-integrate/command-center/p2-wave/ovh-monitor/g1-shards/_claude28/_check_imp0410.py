#!/usr/bin/env python3
"""shard-01 scratch: sanity-run IMP-0410 scenarios + receipt field check."""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "IMP-0410"))
import scenario as S  # noqa: E402

with tempfile.TemporaryDirectory(prefix="imp0410-chk-") as td:
    rows = S.run_all(Path(td))
for k, v in rows.items():
    print(k, v["result"])

doc = json.loads((REPO / "command-center/receipts/IMP-0410.json").read_text(encoding="utf-8"))
text = (REPO / "command-center/receipts/IMP-0410.json").read_text(encoding="utf-8")
print("sentinel present:", "SENTINEL:IMP-0410:LEASES-ADVISORY-LOGGED" in text)
print("excerpt n:", len(doc.get("event_log_excerpt") or []))
tests = doc.get("tests") or {}
for key in ("advisory", "unleased_negative_control"):
    print(key, (tests.get(key) or {}).get("pass"))
policy = doc.get("policy") or {}
print("policy advisory:", policy.get("advisory"), "never_refused:", policy.get("writes_never_refused"))
