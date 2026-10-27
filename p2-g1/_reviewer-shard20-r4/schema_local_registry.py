#!/usr/bin/env python3
"""Fully-local schema validation: anchor the cross-tree file:// $ref to the
p2-g1 tree via a referencing Registry, so zero constraint bytes come from
~/source/ast-integrate. Plus both-states proof of the local chain."""
import json
from pathlib import Path
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
import jsonschema

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
AST = "file:///C:/Users/Prekzursil/source/ast-integrate/"

def local_resource(uri):
    if uri.startswith(AST):
        rel = uri[len(AST):]
        p = REPO / rel
        if p.is_file():
            doc = json.loads(p.read_text(encoding="utf-8"))
            return Resource.from_contents(doc, default_specification=DRAFT202012)
    return None

cat = json.loads((REPO/"command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
entries = {u["id"]: u for u in cat["work_units"]}
UNITS = ["RES-0184","RES-0185","RES-0187","RES-0188","RES-0191",
         "RES-0192","RES-0193","SYN-0003","SYN-0007","SYN-0008","SYN-0035","TST-0005"]

registry = Registry(retrieve=local_resource)
allpass = True
mut_ok = True
for uid in UNITS:
    shim = json.loads((REPO/entries[uid]["output_schema"]).read_text(encoding="utf-8"))
    res = Resource.from_contents(shim, default_specification=DRAFT202012)
    v = jsonschema.Draft202012Validator(shim, registry=registry)
    doc = json.loads((REPO/entries[uid]["output_path"]).read_text(encoding="utf-8"))
    try:
        errs = sorted(v.iter_errors(doc), key=lambda x: list(x.absolute_path))
        n = len(errs)
        msg = errs[0].message[:140] if errs else ""
    except Exception as exc:
        n, msg = -1, repr(exc)[:140]
    if n != 0:
        allpass = False
    print("%-9s local-chain errors=%d %s %s" % (uid, n, "PASS" if n == 0 else "FAIL", msg))
    # both-states mutation: inject state=BLOCKED, local chain MUST fire
    mut = json.loads(json.dumps(doc))
    mut["state"] = "BLOCKED"
    merrs = len(list(v.iter_errors(mut)))
    if merrs == 0:
        mut_ok = False
        print("   !! mutation state=BLOCKED went UNDETECTED by local chain")
print()
print("LOCAL-CHAIN:", "PASS" if allpass else "FAIL", "| BOTH-STATES(fires on BLOCKED):",
      "PASS" if mut_ok else "FAIL")
