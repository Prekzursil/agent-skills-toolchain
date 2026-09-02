#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

p = Path(__file__).with_name("_shard06_compact.json")
rows = json.loads(p.read_text(encoding="utf-8"))
print("n", len(rows))
for r in rows:
    froms = ",".join(r["froms"][:8])
    print(
        f"{r['id']:10} art={int(r['artifact_exists'])} "
        f"probes={len(r['probe_files'])} helpers={len(r['helpers'])} "
        f"missing={len(r['missing_probe_py'])} froms={froms}"
    )
