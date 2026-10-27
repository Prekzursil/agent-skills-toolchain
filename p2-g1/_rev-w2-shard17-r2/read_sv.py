#!/usr/bin/env python3
"""Full schema_validation note of RES-0020."""
import json
import pathlib

REPO = pathlib.Path(r"C:\Users\Prekzursil\p2-g1")
doc = json.loads((REPO / "command-center/research/RES-0020.json").read_text(encoding="utf-8"))
print(json.dumps(doc.get("schema_validation"), indent=1))
