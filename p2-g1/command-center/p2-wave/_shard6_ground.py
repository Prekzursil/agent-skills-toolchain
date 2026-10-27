#!/usr/bin/env python3
"""Gather exact ground truth for probe design."""
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")

print("== live tree facts ==")
for p in ("tools/lib", "origin.lib", "origin.tests", "command-center/TEST-REGISTRY.json",
          "command-center/catalog-slices/BLD-1.json", "command-center/schema/traceability-matrix.schema.json"):
    q = REPO / p
    print(f"  {p}: exists={q.exists()}")

r = subprocess.run(["git", "-C", str(REPO), "log", "--oneline", "-3"],
                   capture_output=True, text=True)
print("  git:", (r.stdout or r.stderr).strip()[:200])

print("== receipt observation values ==")
for uid in ("BLD-0027", "BLD-0028", "BLD-0040", "BLD-0042"):
    d = json.loads(
        (REPO / "command-center/receipts" / f"{uid}.json").read_text(encoding="utf-8")
    )
    rep = d.get("report") or {}
    print(f"  {uid} report.kind={rep.get('kind')}")
    for o in rep.get("observations") or []:
        print("    OBS:", json.dumps(o, ensure_ascii=False)[:440])
