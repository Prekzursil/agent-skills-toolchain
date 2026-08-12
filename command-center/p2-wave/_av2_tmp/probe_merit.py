"""Does the MERIT half of `looks_like_schema_doc` (check_schema) ever fire, and is the natural
fix -- recursing `contract_discriminates` onto the artifact-as-contract -- actually viable?

The build's docstring claims the function "rejects all three garbage probes AND a
structurally-broken schema ({'type': 123, 'required': 'not-an-array'})". Both halves of that
sentence are tested here against the KEYED form, because the unkeyed form is rejected by the
one-line key check and therefore measures the key, not check_schema.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location("ru", REPO / "command-center/ready_units.py")
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()
META = "https://json-schema.org/draft/2020-12/schema"

print("--- A. the docstring's OWN broken-schema example, keyed and unkeyed ---")
broken = {"type": 123, "required": "not-an-array"}
print(f"  unkeyed  {broken}                       -> {ru.looks_like_schema_doc(broken)}")
bk = dict(broken, **{"$schema": META})
print(f"  KEYED    same doc + $schema                  -> {ru.looks_like_schema_doc(bk)}")
print("  (if the unkeyed one is rejected by the KEY check, the docstring's control")
print("   was never exercising check_schema at all)")

print("\n--- B. is the accepted garbage actually a USABLE schema? (validate something with it) ---")
import jsonschema  # noqa: E402

for label, doc in [
    ("garbage + $schema", {"$schema": META, "totally": "unrelated", "passing_tests": 999999}),
    ("bare {$schema}", {"$schema": META}),
]:
    v = jsonschema.Draft202012Validator(doc)
    rejects = [len(list(v.iter_errors(p))) for p in ru._GARBAGE_PROBES]
    print(f"  {label:22s} used AS a contract -> errors per garbage probe = {rejects}")

print("\n--- C. viability of the natural fix: is the REAL WFA-0001 pack itself discriminating? ---")
catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = catalog["work_units"] if isinstance(catalog, dict) else catalog
w = next(x for x in units if x["id"] == "WFA-0001")
pack = json.loads((REPO / w["output_path"]).read_text(encoding="utf-8"))
print(f"  pack top-level keys: {sorted(pack)[:12]}")
try:
    v = jsonschema.Draft202012Validator(pack)
    rejects = [len(list(v.iter_errors(p))) for p in ru._GARBAGE_PROBES]
    print(f"  pack used AS a contract -> errors per garbage probe = {rejects}")
    print(f"  pack DISCRIMINATES = {all(r > 0 for r in rejects)}")
except Exception as e:
    print(f"  pack unusable as a contract: {type(e).__name__}: {e}")

print("\n--- D. would the natural fix (require the artifact-as-schema to discriminate) keep")
print("       WFA-0001 delivered? If not, the cheap fix is NOT drop-in. ---")
