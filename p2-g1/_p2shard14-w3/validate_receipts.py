import json
from pathlib import Path
from jsonschema import Draft202012Validator

REPO = Path.home() / "p2-g1"
ids = ['IMP-0430','IMP-0435','IMP-0437','IMP-0439','IMP-0442','IMP-0448','IMP-0450','IMP-0460','IMP-0466','IMP-0467','IMP-0468','IMP-0470']
schema = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
core = schema["$defs"]["receipt_core"]
v = Draft202012Validator(core)
any_fail = False
for i in ids:
    doc = json.loads((REPO / f"command-center/receipts/{i}.json").read_text(encoding="utf-8"))
    errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        any_fail = True
        print(f"{i}: {len(errs)} schema errors")
        for e in errs[:5]:
            print("   ", list(e.path), e.message[:160])
    else:
        print(f"{i}: schema OK (receipt_core)")
print("ALL-SCHEMA-OK" if not any_fail else "SCHEMA-FAILURES-PRESENT")
