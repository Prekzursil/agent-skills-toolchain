#!/usr/bin/env python3
"""What do the 12 artifacts' own schema_validation blocks claim vs reality?"""
import json
import pathlib

REPO = pathlib.Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["RES-0020", "RES-0037", "RES-0044", "RES-0049", "RES-0077", "RES-0079",
         "RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111"]
for uid in UNITS:
    p = REPO / "command-center" / "research" / f"{uid}.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    sv = doc.get("schema_validation")
    if sv is None:
        print(f"{uid}: no schema_validation block")
    else:
        print(f"{uid}: {json.dumps(sv)[:260]}")
