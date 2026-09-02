#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]


def main() -> None:
    for uid in IDS:
        u = BY.get(uid) or {}
        pdir = WAVE / "probes" / uid
        helpers = sorted(
            p.name
            for p in pdir.iterdir()
            if p.suffix == ".py" and not p.name.startswith("probe")
        )
        print("=" * 72)
        print(uid)
        print("title:", (u.get("title") or u.get("name") or "")[:160])
        print("output:", u.get("output_path"))
        print("sentinel:", u.get("completion_sentinel"))
        print("helpers:", helpers)
        for hp in helpers:
            path = pdir / hp
            text = path.read_text(encoding="utf-8", errors="replace")
            print(f"  helper {hp} lines={text.count(chr(10))+1}")


if __name__ == "__main__":
    main()
