"""Round-3 orientation probe: what do the NON-.json units declare, and what API does the
schema resolver expose? Both are load-bearing for the two confirmed defects:

  D1 wants a registry so a schema-document can be checked for real discrimination instead of
     being waved through by an unresolvable-$ref exception;
  D2 wants to know whether a .md row declares anything a gate could actually check.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
units = catalog["work_units"]

nonjson = [
    u
    for u in units
    if isinstance(u.get("output_path"), str)
    and not u["output_path"].lower().endswith(".json")
]
print(f"units={len(units)}  non-json output_path={len(nonjson)}")

keys: Counter = Counter()
for u in nonjson:
    keys.update(u.keys())
print("\n--- keys present on NON-json rows (count / %d) ---" % len(nonjson))
for k, n in keys.most_common():
    print(f"  {n:5d}  {k}")

print("\n--- one full NON-json row, verbatim ---")
print(json.dumps(nonjson[0], indent=1)[:2600])

print("\n--- do non-json rows declare a sentinel-like token? ---")
sent = [u for u in nonjson if u.get("sentinel")]
print(f"  rows with a truthy 'sentinel': {len(sent)}")
if sent:
    print("  sample sentinels:", [u["sentinel"] for u in sent[:5]])

print("\n--- resolver API ---")
p = REPO / "platform/lib/schema_resolver.py"
spec = importlib.util.spec_from_file_location("schema_resolver", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("  public names:", [n for n in dir(mod) if not n.startswith("__")])
