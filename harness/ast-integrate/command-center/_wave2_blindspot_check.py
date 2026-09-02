#!/usr/bin/env python
"""Residual check demanded by this audit's own disclosed blind spot: my classifier files any doc
lacking `stages` as a REPORT rather than an invalid blueprint. So: does any of the 24
report-classified files actually look like a blueprint that lost a required field?"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, "C:/Users/Prekzursil/source/ast-integrate/platform/lib")
from wfdsl import schemas  # noqa: E402

root = pathlib.Path("C:/Users/Prekzursil/source/ast-integrate/platform/workflows")
wf = schemas.workflow_validator()
BP = {"dsl_version", "stages"}
MARKS = ("dsl_version", "id", "name", "version", "stages", "kind", "roles", "gates", "flagship")

susp = []
for p in sorted(root.rglob("*.json")):
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or BP <= set(d):
        continue
    marks = [k for k in MARKS if k in d]
    if "dsl_version" in marks or "stages" in marks or len(marks) >= 4:
        errs = schemas.error_summary(
            sorted(wf.iter_errors(d), key=lambda e: list(e.absolute_path)), 3
        )
        susp.append({"file": p.name, "blueprint_keys": marks, "validator_errors": errs})

print("report-classified files carrying blueprint-ish keys:", len(susp))
for s in susp:
    print("  ", s["file"], "keys=", s["blueprint_keys"])
    print("      errs=", s["validator_errors"])

def keys_of(p: pathlib.Path) -> set:
    d = json.loads(p.read_text(encoding="utf-8"))
    return set(d) if isinstance(d, dict) else set()


tl = [p for p in root.glob("*.json") if BP <= keys_of(p)]
print()
print("INDEPENDENT top-level blueprint count (non-recursive glob):", len(tl))
print("total top-level json files:", len(list(root.glob("*.json"))))
print("md files:", [p.name for p in root.glob("*.md")])
