#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
UID = "CNF-0001"
OUT = "command-center/schema/confirmation-receipt.schema.json"
path = REPO / OUT
raw = path.read_bytes().replace(b"\r\n", b"\n")
sha = hashlib.sha256(raw).hexdigest()
man_path = REPO / "command-center" / "p2-wave" / "probes" / UID / "UNIT-ARTIFACT-MANIFEST.json"
man = json.loads(man_path.read_text(encoding="utf-8"))
changed = 0
for a in man.get("artifacts") or []:
    if str(a.get("path") or "").replace("\\", "/") == OUT:
        a["sha256"] = sha
        a["bytes"] = len(raw)
        a["present"] = True
        a["unit_id"] = UID
        changed += 1
man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
print("sha", sha, "bytes", len(raw), "rows", changed)
