"""In-process validation of a sample of estate receipts (validator proven equivalent to the gate)."""
import json, random, copy
from pathlib import Path
from jsonschema import Draft202012Validator

REPO = Path.home() / "p2-g1"
full = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
wrapper = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "allOf": [{"$ref": "#/$defs/receipt_core"}],
    "$defs": full.get("$defs", {}),
}
v = Draft202012Validator(wrapper)
recs = sorted((REPO / "command-center/receipts").glob("*.json"))
print("total receipts:", len(recs))
random.seed(42)
sample = random.sample(recs, 40)
ok = 0
ok_files = []
for p in sample:
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    errs = list(v.iter_errors(doc))
    if not errs:
        ok += 1
        ok_files.append(p.name)
print(f"sample of 40: {ok} pass receipt_core")
print("passing:", ok_files[:10])
