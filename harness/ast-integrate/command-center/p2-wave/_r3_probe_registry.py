"""Round-3: can the artifact-as-contract check pass on MERIT rather than by exception?

The adversarial verifier's candidate remedy for D1 treats a raise as a refusal, which is the
module's existing convention -- but it means the program's single delivered unit (WFA-0001) would
be admitted because its `$ref` is UNRESOLVABLE, not because it rejects anything. That is a
detector passing for the wrong reason. `platform/lib/schema_resolver.build_registry()` exists;
if the registry resolves that `$ref`, the check becomes a real discrimination test.

Three states measured here, so the answer cannot be a single reading:
  (a) WFA-0001 pack WITHOUT a registry   -- expect RAISE (unresolvable)
  (b) WFA-0001 pack WITH the registry    -- expect real errors on garbage, i.e. discriminates
  (c) the bypass documents WITH registry -- must still be vacuous (0 errors on garbage)
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import jsonschema

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
spec = importlib.util.spec_from_file_location(
    "ru", REPO / "command-center/ready_units.py"
)
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)
resolver = ru._load_resolver()

registry = None
try:
    registry = resolver.build_registry()
    print(f"registry built: {type(registry).__name__}")
except Exception as e:
    print(f"registry FAILED: {type(e).__name__}: {e}")

catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
w = next(u for u in catalog["work_units"] if u["id"] == "WFA-0001")
pack = json.loads((REPO / w["output_path"]).read_text(encoding="utf-8"))

META = "https://json-schema.org/draft/2020-12/schema"
DOCS = [
    ("WFA-0001 real pack", pack),
    (
        "garbage + $schema",
        {"$schema": META, "totally": "unrelated", "passing_tests": 999999},
    ),
    ("bare {$schema}", {"$schema": META}),
    ("2000-x blob + $schema", {"$schema": META, "blob": "x" * 2000}),
]

for label, doc in DOCS:
    for reg_on in (False, True):
        try:
            v = (
                jsonschema.Draft202012Validator(doc, registry=registry)
                if reg_on and registry is not None
                else jsonschema.Draft202012Validator(doc)
            )
        except Exception as e:
            print(
                f"  {label:24s} registry={reg_on!s:5s} CONSTRUCT-RAISED {type(e).__name__}"
            )
            continue
        cells = []
        for probe in ru._GARBAGE_PROBES:
            try:
                cells.append(str(len(list(v.iter_errors(probe)))))
            except Exception as e:
                cells.append(f"RAISE:{type(e).__name__[:22]}")
        print(
            f"  {label:24s} registry={reg_on!s:5s} errors-per-garbage-probe = {cells}"
        )
