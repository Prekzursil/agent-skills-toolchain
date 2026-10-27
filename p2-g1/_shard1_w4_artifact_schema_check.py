#!/usr/bin/env python3
"""Shard1-w4: schema-check every unit's artifact against its catalog output_schema."""
import importlib.util, json, subprocess, sys
from pathlib import Path

REPO = Path(".").resolve()
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS_BY_ID = {u["id"]: u for u in CAT["work_units"]}
MINE = ["ADV-0127", "ADV-0128", "ARC-0001", "ARC-0012", "ARC-0013", "ARC-0015",
        "ARC-0019", "ARC-0020", "ARC-0021", "ARC-0047", "ARC-0048", "ARC-0054"]

for uid in MINE:
    out_rel = str(UNITS_BY_ID[uid]["output_path"]).replace("\\", "/")
    sch = str(UNITS_BY_ID[uid]["output_schema"]).replace("\\", "/")
    p = subprocess.run([sys.executable, "-I", "-B", "platform/lib/schema_resolver.py",
                        out_rel, sch], cwd=str(REPO), capture_output=True, text=True, timeout=600)
    tail = ((p.stdout or "") + (p.stderr or "")).strip()
    n = tail.count("\n") + 1 if tail else 0
    print(f"{uid}: rc={p.returncode} errlines={n}")
    if p.returncode != 0:
        for line in tail.splitlines()[:8]:
            print("   ", line[:150])
