import json
from pathlib import Path
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from jsonschema import Draft202012Validator

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
AST = "file:///C:/Users/Prekzursil/source/ast-integrate/"

def load(rel):
    return json.loads((REPO/rel).read_text(encoding="utf-8"))

# Registry mapping the ast-integrate file:// URIs to p2-g1 files
resources = {}
for rel in ["platform/schema/artifact-class-profiles.schema.json",
            "platform/schema/receipt.schema.json"]:
    doc = load(rel)
    res = Resource.from_contents(doc, default_specification=DRAFT202012)
    resources[AST + rel] = res
registry = Registry(resources=resources)

UNITS = {
 'CNF-0173': ('command-center/receipts/CNF-0173.json', 'command-center/schema/confirmation-record.schema.json'),
 'CNF-0177': ('command-center/receipts/CNF-0177.json', 'command-center/schema/confirmation-record.schema.json'),
 'CNF-0178': ('command-center/receipts/CNF-0178.json', 'command-center/schema/confirmation-record.schema.json'),
 'CNF-0180': ('command-center/receipts/CNF-0180.json', 'command-center/schema/confirmation-record.schema.json'),
 'CNF-0188': ('command-center/receipts/CNF-0188.json', 'command-center/schema/program-gate-report.schema.json'),
 'CNL-0076': ('command-center/design/council/CNL-0076-stopping-expression-runtime-evaluation-semantics.schema.json', 'command-center/schema/councilspec.v2.schema.json'),
 'IMP-0003': ('command-center/receipts/IMP-0003.json', 'command-center/schema/receipt.schema.json'),
 'IMP-0013': ('command-center/receipts/IMP-0013.json', 'command-center/schema/receipt.schema.json'),
 'IMP-0014': ('command-center/receipts/IMP-0014.json', 'command-center/schema/receipt.schema.json'),
 'IMP-0018': ('command-center/receipts/IMP-0018.json', 'command-center/schema/receipt.schema.json'),
 'IMP-0020': ('command-center/receipts/IMP-0020.json', 'command-center/schema/receipt.schema.json'),
 'IMP-0022': ('command-center/receipts/IMP-0022.json', 'command-center/schema/receipt.schema.json'),
}
failures = []
for uid, (art_rel, sch_rel) in UNITS.items():
    art = load(art_rel)
    sch = load(sch_rel)
    try:
        v = Draft202012Validator(sch, registry=registry)
        errs = sorted(v.iter_errors(art), key=lambda e: list(e.absolute_path))
        if errs:
            failures.append(f"{uid}: SCHEMA INVALID ({len(errs)} errors)")
            for e in errs[:3]:
                failures.append(f"   at {list(e.absolute_path)}: {e.message[:180]}")
        else:
            print(f"{uid}: schema VALID")
    except Exception as exc:
        failures.append(f"{uid}: validator exception {type(exc).__name__}: {exc}")
print()
if failures:
    for f in failures: print("FAIL:", f)
else:
    print("ALL 12 ARTIFACTS SCHEMA-VALID against catalog output_schema")
