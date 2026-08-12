"""AUDIT (independent): is the per-unit schema check VACUOUS for IMP-0433?

Both-states test, PER UNIT. The builder's control ran only on AUD-0020 (audit-inventory.schema.json).
A control on one unit's schema says nothing about a DIFFERENT unit's schema.

For each of the 5 units: validate (a) the real artifact, (b) a garbage doc, (c) the artifact with
its `sentinel` field removed. A schema that accepts (b) is a NO-OP gate for that unit.
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

CAT = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by = {u["id"]: u for u in CAT["work_units"]}

GARBAGE = {"totally": "unrelated", "nonsense": [1, 2, 3], "n": 999999}

print(
    f"{'unit':<10} {'declared output_schema':<52} {'real':<6} {'GARBAGE':<9} {'no-sentinel':<12} verdict"
)
print("-" * 118)
for uid in ["IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020"]:
    u = by[uid]
    schema = u["output_schema"]
    doc = json.loads((REPO / u["output_path"]).read_text(encoding="utf-8"))
    stripped = {k: v for k, v in doc.items() if k != "sentinel"}

    def n(d):
        try:
            return len(mod.validate_artifact(d, schema))
        except Exception as e:
            return f"ERR:{type(e).__name__}"

    e_real, e_garb, e_strip = n(doc), n(GARBAGE), n(stripped)
    vacuous = e_real == 0 and e_garb == 0 and e_strip == 0
    print(
        f"{uid:<10} {schema:<52} {str(e_real):<6} {str(e_garb):<9} {str(e_strip):<12} "
        f"{'*** VACUOUS - accepts garbage ***' if vacuous else 'discriminates'}"
    )

print()
print(
    "Interpretation: a schema returning 0 errors for the GARBAGE column cannot distinguish"
)
print(
    "the real artifact from unrelated JSON, so 'schema-VALID' carries no information there."
)
