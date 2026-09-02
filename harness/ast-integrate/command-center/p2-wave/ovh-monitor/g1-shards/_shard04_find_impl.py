#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

EXTRACT = Path(__file__).resolve().parent.parent / "error-pull" / "extracted"
IDS = [
    ln.strip()
    for ln in Path(__file__).with_name("shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
hits = []
for host in sorted(EXTRACT.iterdir()):
    probes = host / "probes"
    if not probes.is_dir():
        continue
    for uid in IDS:
        d = probes / uid
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in {".py", ".json"}:
                continue
            size = p.stat().st_size
            if size < 400:
                continue
            if p.suffix == ".py":
                head = p.read_text(encoding="utf-8", errors="replace")[:120]
                if "g1-mod: real-surface" in head or "g1-surface: generated" in head:
                    continue
            hits.append((size, f"{host.name}/probes/{uid}/{p.relative_to(d).as_posix()}"))
hits.sort(reverse=True)
for size, rel in hits[:100]:
    print(f"{size:7d} {rel}")
print("n", len(hits))
