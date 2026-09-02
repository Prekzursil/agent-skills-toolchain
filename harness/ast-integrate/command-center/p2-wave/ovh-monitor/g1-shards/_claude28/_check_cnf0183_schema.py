#!/usr/bin/env python3
"""shard-01 scratch: verify CNF-0183 schema rejects garbage, accepts receipt."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "CNF-0183"))
import schema_check as SC  # noqa: E402

print("garbage_rejected:", SC.garbage_rejected(REPO))
doc = json.loads((REPO / "command-center/receipts/CNF-0183.json").read_text(encoding="utf-8"))
errs = SC.error_messages(doc, REPO)
print("receipt errors:", len(errs))
for e in errs[:5]:
    print(" ", e[:200])
# also re-check CNF-0182's artifact if present, since it shares the class
p182 = REPO / "command-center/receipts/CNF-0182.json"
if p182.is_file():
    d182 = json.loads(p182.read_text(encoding="utf-8"))
    e182 = SC.error_messages(d182, REPO)
    print("CNF-0182 receipt errors:", len(e182))
    for e in e182[:3]:
        print(" ", e[:200])
else:
    print("CNF-0182 receipt not at command-center/receipts/CNF-0182.json")
