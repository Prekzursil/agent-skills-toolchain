#!/usr/bin/env python3
"""Print output_path, sentinel, and named probe commands for unit IDs."""
import json
import sys
from pathlib import Path

REPO = Path("/mnt/c/Users/Prekzursil/source/ast-integrate")
CATALOG = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u["id"]: u for u in CATALOG["work_units"]}

for uid in sys.argv[1:]:
    u = UNITS.get(uid)
    if not u:
        print(uid, "NOT-IN-CATALOG")
        continue
    print("==", uid)
    print(" output_path:", u.get("output_path"))
    print(" sentinel:", u.get("completion_sentinel"))
    ret = REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
    if ret.is_file():
        doc = json.loads(ret.read_text(encoding="utf-8"))
        probes = doc.get("named_probes") or doc.get("probes") or []
        for p in probes:
            if isinstance(p, dict):
                print(" probe:", p.get("command"))
            else:
                print(" probe:", p)
