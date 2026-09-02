#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
PULL = HERE.parent / "delivery-pull"
IDS = [
    ln.strip()
    for ln in (HERE / "shard-04.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip()
]
REPO = HERE.parents[3]
LIVE = REPO / "command-center" / "p2-wave" / "probes"

hosts = sorted(p for p in PULL.iterdir() if p.is_dir())
print(f"hosts={len(hosts)}")
for uid in IDS:
    live = LIVE / uid
    live_py = sorted(p.name for p in live.glob("*.py")) if live.is_dir() else []
    ovh = []
    for host in hosts:
        for cand in (
            host / "delta" / "command-center" / "p2-wave" / "probes" / uid,
            host / "tree" / "command-center" / "p2-wave" / "probes" / uid,
        ):
            if cand.is_dir():
                names = sorted(p.name for p in cand.iterdir())
                ovh.append({"host": host.name, "rel": str(cand.relative_to(PULL)).replace("\\", "/"), "n": len(names), "py": [n for n in names if n.endswith(".py")]})
    if not live_py or any(h["py"] and set(h["py"]) - set(live_py) for h in ovh):
        print(f"{uid} live_py={live_py}")
        for h in ovh:
            extra = sorted(set(h["py"]) - set(live_py))
            print(f"  {h['host']} n={h['n']} extra={extra} py={h['py']}")
