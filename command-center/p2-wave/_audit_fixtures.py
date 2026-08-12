"""AUDIT (independent): validate the 13 IMP-0433 fixtures MYSELF against the receipt schema.

The builder's claim is 12/12 negative fixtures INVALID + 1 positive VALID, each negative failing on
its OWN mutation (attribution). I re-validate from disk with my own loop and print the actual error
paths so attribution can be checked rather than trusted.
"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
p = REPO / "platform" / "lib" / "schema_resolver.py"
sys.path.insert(0, str(p.parent))
spec = importlib.util.spec_from_file_location("schema_resolver", p)
mod = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver"] = mod
spec.loader.exec_module(mod)

FIX = REPO / "command-center/p2-wave/fixtures/IMP-0433"
SCHEMA = "command-center/schema/receipt.schema.json"

if not FIX.is_dir():
    print(f"FAILED: fixture dir absent: {FIX}")
    raise SystemExit(1)

files = sorted(FIX.glob("*.json"))
print(f"fixture files on disk: {len(files)}")
print(f"validating against   : {SCHEMA}")
print()

pos_ok = None
neg_invalid = 0
neg_total = 0
for f in files:
    doc = json.loads(f.read_text(encoding="utf-8"))
    errs = mod.validate_artifact(doc, SCHEMA)
    kind = "POSITIVE" if "positive" in f.name else "negative"
    if kind == "POSITIVE":
        pos_ok = (len(errs) == 0)
    else:
        neg_total += 1
        if errs:
            neg_invalid += 1
    first = ""
    if errs:
        e = errs[0]
        loc = getattr(e, "json_path", None) or "/".join(str(x) for x in getattr(e, "absolute_path", []))
        msg = str(getattr(e, "message", e))
        first = f"{loc}: {msg[:78]}"
    print(f"  {f.name:<26} {kind:<9} errors={len(errs):<3} {first}")

print()
print(f"  positive fixture VALID      : {pos_ok}          (builder: VALID)")
print(f"  negatives INVALID           : {neg_invalid}/{neg_total}      (builder: 12/12)")

print()
print("ATTRIBUTION GUARD (my own): a negative only proves its condition if the POSITIVE base is clean.")
print(f"  base clean? {pos_ok}")
