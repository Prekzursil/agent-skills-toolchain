"""What exactly must the reviewer re-measure for IMP-0440, TST-0334, TST-0350?"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
for uid, rel in (
    ("IMP-0440", "command-center/receipts/IMP-0440.json"),
    ("TST-0334", "command-center/receipts/TST-0334.json"),
    ("TST-0350", "command-center/receipts/TST-0350.json"),
):
    d = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    print("=" * 100)
    print(f"{uid}  state={d.get('state')}")
    print(f"  artifacts: {[a.get('path') for a in (d.get('artifacts') or [])]}")
    for i, e in enumerate(d.get("evidence") or []):
        print(f"  evidence[{i}] claim: {str(e.get('claim'))[:300]}")
        for pr in e.get("probes") or []:
            print(f"      [{pr.get('role')}] {str(pr.get('command'))[:170]}")
            print(f"         out: {str(pr.get('raw_output'))[:260]}")
    for i, c in enumerate(d.get("negative_controls") or []):
        print(f"  control[{i}]: {json.dumps(c)[:420]}")
    for t in d.get("tests") or []:
        print(f"  test: {json.dumps(t)[:300]}")
    print(f"  failure: {json.dumps(d.get('failure'))[:400]}")
