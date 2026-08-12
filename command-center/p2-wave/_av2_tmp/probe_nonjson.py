"""Attack angle NEITHER report examined: `artifact_delivered` short-circuits on suffix.

    if fp.suffix.lower() != ".json":
        return True, "non-json-present"

For any unit whose declared output_path is not *.json, the predicate degenerates to
exists() AND size>0 -- the exact Goodhart predicate this module's docstring says it replaced.
Conditions 3 (parses), 4 (schema-valid), 4b (contract can fail) and 5 (no self-declared failure)
are all skipped. Measure the population, then execute the false green on a scratch path.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()

catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = catalog["work_units"] if isinstance(catalog, dict) else catalog

suffixes = Counter()
nonjson = []
for u in units:
    p = u.get("output_path")
    if not p:
        suffixes["<none>"] += 1
        continue
    s = Path(p).suffix.lower() or "<no-suffix>"
    suffixes[s] += 1
    if s != ".json":
        nonjson.append(u)

print("--- A. population: declared output_path suffixes over the 2,007 units ---")
for s, n in suffixes.most_common():
    print(f"  {s:14s} {n}")
print(f"  NON-.json units (predicate degenerates to exists+size): {len(nonjson)}")

print("\n--- B. how many of those already exist on disk, and what does the predicate say? ---")
present = []
for u in nonjson:
    fp = REPO / u["output_path"]
    if fp.exists() and fp.stat().st_size > 0:
        ok, why = ru.artifact_delivered(u, resolver)
        present.append((u["id"], u["output_path"], fp.stat().st_size, ok, why))
print(f"  present + non-empty: {len(present)}")
for row in present[:15]:
    print(f"   {row[0]:11s} {row[2]:8d} B  delivered={row[3]} ({row[4]})")

print("\n--- C. EXECUTE the false green on a scratch non-.json path (no real output_path touched) ---")
rel = "command-center/p2-wave/_av2_tmp/_synthetic_artifact.md"
fp = REPO / rel
fp.write_text("x" * 2000, encoding="utf-8")
# borrow a real non-json unit's declared contract if it has one, else the meta-schema
donor = nonjson[0] if nonjson else {}
unit = {
    "id": "AV2-NONJSON",
    "output_path": rel,
    "output_schema": donor.get("output_schema") or "command-center/schema/receipt.schema.json",
    "state": "BLOCKED",
}
ok, why = ru.artifact_delivered(unit, resolver)
print(f"  2000-x .md file, declared contract={unit['output_schema']}")
print(f"  -> delivered={ok} ({why})")

# CONTROL: the byte-identical payload under a .json name must be REJECTED in the same run,
# otherwise this probe is measuring the content, not the suffix branch.
rel2 = "command-center/p2-wave/_av2_tmp/_synthetic_artifact.json"
fp2 = REPO / rel2
fp2.write_text("x" * 2000, encoding="utf-8")
unit2 = dict(unit, id="AV2-CONTROL", output_path=rel2)
ok2, why2 = ru.artifact_delivered(unit2, resolver)
print(f"  CONTROL same 2000 bytes named .json -> delivered={ok2} ({why2})")
print(f"\n  SUFFIX_BYPASS_PROVEN = {ok is True and ok2 is False}")
fp.unlink(missing_ok=True)
fp2.unlink(missing_ok=True)
