#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXTRACT = HERE.parent / "error-pull" / "extracted"
LIVE = REPO / "command-center" / "p2-wave" / "probes"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
copied = []
skipped = []
for uid in IDS:
    dest = LIVE / uid
    dest.mkdir(parents=True, exist_ok=True)
    live_names = {p.name for p in dest.iterdir()} if dest.is_dir() else set()
    sources = []
    for host in sorted(EXTRACT.iterdir()):
        cand = host / "probes" / uid
        if cand.is_dir():
            sources.append(cand)
    for src in sources:
        for p in src.iterdir():
            if not p.is_file():
                continue
            if p.name in live_names:
                continue
            target = dest / p.name
            shutil.copy2(p, target)
            live_names.add(p.name)
            copied.append(f"{uid}/{p.name} from {src.relative_to(EXTRACT)}")
            print(f"COPY {uid}/{p.name} <- {src.relative_to(EXTRACT)}")
    if not sources:
        skipped.append(uid)

print(f"copied={len(copied)} no-source={skipped}")
