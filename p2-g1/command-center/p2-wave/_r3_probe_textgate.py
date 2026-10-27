"""Round-3: what CAN a text (.md) artifact be gated on, honestly?

D2 (confirmed by the adversarial verifier): `artifact_delivered` returns
`(True, "non-json-present")` for any non-.json output_path that merely exists and is non-empty,
so a 2,000-x blob named .md is DELIVERED while the identical bytes named .json are rejected.

Before writing a gate I measure what the rows actually declare, and whether the JSON-Schema
contract they name could ever be applied to a markdown file at all.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location(
    "ru", REPO / "command-center/ready_units.py"
)
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()
print(f"resolver loaded: {resolver is not None}")

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

suffixes = Counter(Path(u["output_path"]).suffix.lower() for u in nonjson)
print(f"non-json units: {len(nonjson)}  suffixes: {dict(suffixes)}")

have_sentinel = [
    u
    for u in nonjson
    if isinstance(u.get("completion_sentinel"), str)
    and u["completion_sentinel"].strip()
]
print(
    f"rows declaring a non-empty completion_sentinel: {len(have_sentinel)}/{len(nonjson)}"
)
print(f"  sample: {[u['completion_sentinel'] for u in have_sentinel[:4]]}")

# and over the WHOLE catalog, so the gate's applicability is known, not assumed
allsent = sum(
    1
    for u in units
    if isinstance(u.get("completion_sentinel"), str)
    and u["completion_sentinel"].strip()
)
print(
    f"rows declaring a non-empty completion_sentinel, WHOLE catalog: {allsent}/{len(units)}"
)

decls = Counter(u.get("output_schema") for u in nonjson)
print(f"\ndistinct output_schema over the non-json units: {len(decls)}")
for s, n in decls.most_common(8):
    print(f"  {n:4d}  {s}")

print("\n--- can any of those contracts be applied to a markdown STRING? ---")
for s in list(decls)[:8]:
    if not isinstance(s, str) or not s:
        print(f"  {s!r}: no declaration")
        continue
    try:
        errs = resolver.validate_artifact("# a markdown document\n\nsome prose.\n", s)
        print(f"  {s}: errors on a markdown string = {len(errs)}")
    except Exception as e:
        print(f"  {s}: RAISES {type(e).__name__}")

print("\n--- what does the dominant contract actually require? ---")
dom = decls.most_common(1)[0][0]
p = REPO / dom
if p.is_file():
    doc = json.loads(p.read_text(encoding="utf-8"))
    print(f"  {dom}")
    print(f"  type={doc.get('type')!r} required={doc.get('required')}")
    print(f"  $comment={str(doc.get('$comment'))[:300]}")
else:
    print(f"  {dom}: NOT A FILE on disk")
