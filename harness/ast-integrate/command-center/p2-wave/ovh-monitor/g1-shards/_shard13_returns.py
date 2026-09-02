#!/usr/bin/env python3
"""Extract named-probe raw_output tails from SUBAGENT-RETURN.json."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAVE = HERE.parents[1]
IDS = [
    ln.strip()
    for ln in (HERE / "shard-13.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
parts = []
for uid in IDS:
    p = WAVE / "probes" / uid / "SUBAGENT-RETURN.json"
    if not p.is_file():
        parts.append(f"==== {uid} NO RETURN")
        continue
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        parts.append(f"==== {uid} unparseable {exc}")
        continue
    parts.append("=" * 72)
    parts.append(f"{uid} status={doc.get('status') or doc.get('state')}")
    for key in ("named_probes", "probes"):
        for item in doc.get(key) or []:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("raw_output") or item.get("output") or "")
            cmd = str(item.get("command") or "")
            parts.append(f"--- {item.get('id') or item.get('name')} cmd={cmd[-80:]}")
            tail = raw[-2500:] if raw else ""
            parts.append(tail)
dest = HERE / "_shard13_returns.txt"
dest.write_text("\n".join(parts), encoding="utf-8")
print("wrote", dest, "bytes", dest.stat().st_size)
