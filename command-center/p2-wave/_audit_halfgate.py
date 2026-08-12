"""AUDIT (independent): does the resolver silently DROP the second half of an 'A + B' contract?

Method that does not depend on the builder's framing:
  1. Take a real two-schema declaration from the catalog.
  2. Build a doc that is VALID against half A but must be INVALID against half B
     (verified separately by validating it against half B alone).
  3. Validate against the combined 'A + B' string. If it returns 0 errors while half-B-alone
     returns >0, the second half is provably not evaluated.
Both-states: half B alone MUST fire, else the fixture is not diagnostic.
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

CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = CAT["work_units"]
by = {u["id"]: u for u in units}

two = [u for u in units if isinstance(u.get("output_schema"), str) and "+" in u["output_schema"]]
print(f"two-schema units: {len(two)}")
decl = two[0]["output_schema"]
print(f"sample unit  : {two[0]['id']}")
print(f"declared     : {decl}")
halves = [h.strip() for h in decl.split("+")]
print(f"halves       : {halves}")

# Use a real, known-good receipt as the doc (valid against half A = the receipt schema).
doc = json.loads((REPO / "command-center/receipts/IMP-0433.json").read_text(encoding="utf-8"))


def n(d, s):
    try:
        return len(mod.validate_artifact(d, s))
    except Exception as e:
        return f"ERR:{type(e).__name__}"


print()
print(f"  errors vs HALF A alone   ({halves[0]}) : {n(doc, halves[0])}")
print(f"  errors vs HALF B alone   ({halves[1]}) : {n(doc, halves[1])}   <-- must be >0 to be diagnostic")
print(f"  errors vs COMBINED 'A + B'                : {n(doc, decl)}")
print()
print(f"  parse_schema_ref(combined) -> {mod.parse_schema_ref(decl)!r}")
print(f"  parse_schema_ref(half A)   -> {mod.parse_schema_ref(halves[0])!r}")

print()
print("=" * 70)
print("UNRESOLVABLE CENSUS over ALL catalog units (builder claimed 0)")
print("=" * 70)
unres, ok, nodecl = [], 0, 0
for u in units:
    s = u.get("output_schema")
    if not isinstance(s, str) or not s:
        nodecl += 1
        continue
    try:
        mod.validate_artifact({}, s)
        ok += 1
    except Exception as e:
        unres.append((u["id"], s, type(e).__name__))
print(f"  resolvable          : {ok}")
print(f"  no declaration      : {nodecl}")
print(f"  UNRESOLVABLE        : {len(unres)}")
for r in unres[:10]:
    print(f"     {r}")
