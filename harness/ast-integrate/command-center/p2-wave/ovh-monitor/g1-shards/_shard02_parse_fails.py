#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

log = Path(
    r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_shard02_measure.log"
)
text = log.read_text(encoding="utf-8", errors="replace")
blocks = text.split("==== ")
rows = []
for block in blocks:
    if not block.strip():
        continue
    lines = block.splitlines()
    uid = lines[0].strip()
    if uid.startswith("SUMMARY"):
        continue
    last = ""
    for ln in reversed(lines):
        if ln.startswith("FAILED:") or ln.startswith("SUCCESS:"):
            last = ln
            break
    probe_tail = [ln for ln in lines if ln.startswith("  ") or "Error" in ln or "FAILED:" in ln]
    rows.append((uid, last, "\n".join(probe_tail[-12:])))

out = Path(
    r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards\_shard02_fails.txt"
)
parts = []
ok = fail = 0
for uid, last, tail in rows:
    if last.startswith("SUCCESS:delivered"):
        ok += 1
        continue
    fail += 1
    parts.append("=" * 72)
    parts.append(uid)
    parts.append(last)
    parts.append(tail)
out.write_text("\n".join(parts) + "\n", encoding="utf-8")
print(f"ok={ok} fail={fail} wrote {out}")
