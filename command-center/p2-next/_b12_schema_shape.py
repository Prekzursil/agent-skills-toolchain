import json
import pathlib

d = json.loads(
    (
        pathlib.Path(__file__).resolve().parents[2]
        / "platform/schema/receipt.schema.json"
    ).read_text(encoding="utf-8")
)
defs = d["$defs"]
print("DEFS:", sorted(defs.keys()))
for k in (
    "failure_classification_code",
    "vendor_id",
    "probe",
    "evidence_item",
    "manifest_registration",
    "terminal_state",
):
    if k in defs:
        print(f"\n== {k} ==\n{json.dumps(defs[k], indent=1)[:1500]}")
core = defs.get("receipt_core", {})
print(f"\n== core required ==\n{core.get('required')}")
print(f"== core additionalProperties == {core.get('additionalProperties')}")
print(f"== core property names ==\n{sorted((core.get('properties') or {}).keys())}")
for k in ("reviewer", "extensions", "failure", "state", "manifest_registration"):
    p = (core.get("properties") or {}).get(k)
    if p is not None:
        print(f"\n-- core.properties.{k} --\n{json.dumps(p, indent=1)[:1200]}")
# the SUCCESS-conditional rules
for key in ("allOf", "if", "then", "dependentSchemas"):
    if key in core:
        print(f"\n== core.{key} ==\n{json.dumps(core[key], indent=1)[:2500]}")
