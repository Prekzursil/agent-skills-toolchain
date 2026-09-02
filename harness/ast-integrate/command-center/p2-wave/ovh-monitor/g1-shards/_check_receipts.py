#!/usr/bin/env python3
import json
from pathlib import Path

for label, root in (
    ("wsl", Path("/home/prekzursil/p2-g1")),
    ("win", Path("/mnt/c/Users/Prekzursil/source/ast-integrate")),
):
    p = root / "command-center/receipts/IMP-0317.json"
    if not p.is_file():
        print(label, "IMP-0317 missing")
        continue
    doc = json.loads(p.read_text(encoding="utf-8"))
    ev = doc.get("evidence")
    print(label, "IMP-0317", type(ev).__name__, end=" ")
    if isinstance(ev, list):
        print([e.get("id") if isinstance(e, dict) else type(e).__name__ for e in ev[:8]])
    else:
        print()
    p = root / "command-center/receipts/TST-0206.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    ev = doc.get("evidence")
    print(label, "TST-0206", [e.get("id") for e in ev if isinstance(e, dict)][:8] if isinstance(ev, list) else type(ev).__name__)
