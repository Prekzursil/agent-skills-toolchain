#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

p = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_shard02_dump.json")
out = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_shard02_asserts.txt")
rows = json.loads(p.read_text(encoding="utf-8"))
lines: list[str] = []
for r in rows:
    lines.append("=" * 72)
    lines.append(r["id"])
    lines.append(f"title: {r.get('title')}")
    lines.append(f"output: {r.get('output_path')} exists={r.get('out_exists')}")
    lines.append(f"helpers: {r.get('helpers')}")
    lines.append(f"probes: {r.get('probes')}")
    pa = r.get("probe_asserts") or {}
    for name, info in pa.items():
        lines.append(f"-- {name} imports --")
        for imp in info.get("imports") or []:
            lines.append(f"  {imp}")
        lines.append(f"-- {name} asserts --")
        for a in info.get("asserts") or []:
            lines.append(f"  {a}")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", out, "chars", out.stat().st_size)
