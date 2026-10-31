#!/usr/bin/env python3
"""Settle the schema instrument question with a control group.

1. Is worktree receipt.schema.json byte-identical to the source-tree copy?
2. Do EARLIER-wave closed artifacts (already SUCCESS/PASS) validate against
   the SAME generic_report the current control plane delegates to?
"""
import hashlib
import json
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
SRC = Path(r"C:\Users\Prekzursil\source\ast-integrate\platform\schema\receipt.schema.json")
WT = REPO / "platform" / "schema" / "receipt.schema.json"


def sha(p):
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]


print("receipt.schema.json  source:", sha(SRC), "worktree:", sha(WT), "identical:", sha(SRC) == sha(WT))
doc = json.loads(WT.read_text(encoding="utf-8"))
gr = doc.get("$defs", {}).get("generic_report")
print("generic_report present in worktree copy:", gr is not None)
if gr is not None:
    # resolve internal refs locally
    wrapper = {"allOf": [{"$ref": "#/$defs/generic_report"}], "$defs": doc.get("$defs") or {}}
    v = jsonschema.validators.validator_for(wrapper)(wrapper)
    for uid in ["ADV-0020", "ADV-0012", "ADV-0031", "IMP-0001"]:
        p = None
        for cand in REPO.glob(f"command-center/**/{uid}-*.json"):
            p = cand
            break
        if not p:
            print(uid, "artifact not found")
            continue
        art = json.loads(p.read_text(encoding="utf-8"))
        errs = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:120]}" for e in v.iter_errors(art)]
        print(f"{uid}: {'PASS' if not errs else f'FAIL({len(errs)})'}  first: {errs[0] if errs else '-'}")
