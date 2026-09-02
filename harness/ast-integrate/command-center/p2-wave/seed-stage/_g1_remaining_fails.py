#!/usr/bin/env python3
"""Emit remaining-fail IDs: latest g1-local-full.jsonl overlaid with repair-claude/*.jsonl."""
import json
import sys
from pathlib import Path

MON = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor")
latest = {}
for src in [MON / "g1-local-full.jsonl", MON / "g1-fails-rerun.jsonl", *sorted((MON / "repair-claude").glob("*.jsonl"), key=lambda p: p.stat().st_mtime)]:
    if not src.is_file():
        continue
    for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        latest[rec.get("id")] = rec

fails = sorted(uid for uid, rec in latest.items() if not rec.get("ok"))
out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
text = "\n".join(fails) + "\n"
if out:
    out.write_text(text, encoding="utf-8")
print(f"total={len(latest)} fails={len(fails)}", file=sys.stderr)
if not out:
    sys.stdout.write(text)
