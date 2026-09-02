#!/usr/bin/env python3
"""Copy missing fixture dirs for restored ADV probe trees."""
from __future__ import annotations

import shutil
from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]
LIVE = WAVE / "probes"
EP = WAVE / "ovh-monitor" / "error-pull"
UIDS = ["ADV-0068", "ADV-0090", "ADV-0113"]


def main() -> None:
    roots = []
    for kind in ("extracted-delta", "extracted"):
        base = EP / kind
        if not base.is_dir():
            continue
        for box in base.iterdir():
            d = box / "probes"
            if d.is_dir():
                roots.append(d)
    for uid in UIDS:
        dest = LIVE / uid / "fixtures"
        found = None
        best = 0
        for root in roots:
            src = root / uid / "fixtures"
            if src.is_dir():
                n = sum(1 for _ in src.rglob("*"))
                if n > best:
                    best = n
                    found = src
        print(uid, "dest_exists", dest.is_dir(), "harvest", found, "n", best)
        if found is None:
            continue
        if dest.is_dir():
            continue
        shutil.copytree(found, dest)
        print("  copied fixtures", dest)


if __name__ == "__main__":
    main()
