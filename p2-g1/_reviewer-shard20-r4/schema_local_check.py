#!/usr/bin/env python3
"""Schema re-verification: validate each artifact against the LOCAL physical
profile $defs class directly (no cross-tree $ref), and prove constraint presence."""
import json
from pathlib import Path
import jsonschema

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CLASS = {
    "RES-0184": "measurement-run", "RES-0185": "measurement-run",
    "RES-0187": "measurement-run", "RES-0188": "measurement-run",
    "RES-0191": "design-spec", "RES-0192": "measurement-run",
    "RES-0193": "measurement-run", "SYN-0003": "rival-hypothesis",
    "SYN-0007": "intervention-ranking", "SYN-0008": "synthesis-candidate",
    "SYN-0035": "calibration-report", "TST-0005": "fault-injection-receipt",
}
# derive class from each shim's x-artifact-class rather than hardcoding
cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
entries = {u["id"]: u for u in cat["work_units"]}
profile = json.loads((REPO/"platform/schema/artifact-class-profiles.schema.json").read_text(encoding="utf-8"))
defs = profile.get("$defs", {})
print("profile $defs classes:", sorted(defs.keys())[:30])
print()
allpass = True
for uid in UNITS if (UNITS := list(CLASS)) else CLASS:
    shim = json.loads((REPO/entries[uid]["output_schema"]).read_text(encoding="utf-8"))
    cls = shim.get("x-artifact-class")
    d = defs.get(cls)
    if d is None:
        print(uid, "FAIL: class", cls, "missing from profile $defs"); allpass = False; continue
    nreq = len(d.get("required", []) or [])
    nprops = len(d.get("properties", {}) or {})
    # count total constraint keywords in the class subtree
    def count_kw(node):
        n = 0
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("required","properties","patternProperties","enum","const","minItems",
                         "minimum","pattern","type","additionalProperties","oneOf","anyOf","allOf",
                         "items","minLength","format","uniqueItems","if","then","else","not",
                         "dependentRequired","propertyNames","multipleOf","exclusiveMinimum"):
                    n += 1
                n += count_kw(v)
        elif isinstance(node, list):
            for v in node: n += count_kw(v)
        return n
    kw = count_kw(d)
    doc = json.loads((REPO/entries[uid]["output_path"]).read_text(encoding="utf-8"))
    v = jsonschema.Draft202012Validator(d)
    errs = sorted(v.iter_errors(doc), key=lambda x: list(x.absolute_path))
    status = "PASS" if not errs else "FAIL"
    if errs: allpass = False
    print("%-9s class=%-24s required=%d props=%d constraint-kw=%d errors=%d %s" %
          (uid, cls, nreq, nprops, kw, len(errs), status))
    for e in errs[:3]:
        print("   !!", list(e.absolute_path)[:4], e.message[:160])
print()
print("ALL-SCHEMAS:", "PASS" if allpass else "FAIL")
