#!/usr/bin/env python3
"""Find harvest copies of missing shard-07 probe scripts. No repo-wide rglob."""
from __future__ import annotations

from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]  # command-center/p2-wave
UIDS = ["ADV-0068", "ADV-0090", "ADV-0113"]
ROOTS = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "scw-pull",
    WAVE / "scw-pull",
]


def main() -> None:
    print("WAVE", WAVE)
    hits = 0
    for root in ROOTS:
        print("root", root, "exists", root.is_dir())
        if not root.is_dir():
            continue
        for box in sorted(root.iterdir()):
            if not box.is_dir():
                continue
            for sub in ("tree", "delta"):
                probes = box / sub / "command-center" / "p2-wave" / "probes"
                if not probes.is_dir():
                    continue
                for uid in UIDS:
                    d = probes / uid
                    if not d.is_dir():
                        continue
                    pys = [p.name for p in d.iterdir() if p.is_file() and p.suffix == ".py"]
                    if pys:
                        print("HIT", box.name, sub, uid, pys)
                        hits += 1
                    else:
                        names = [p.name for p in d.iterdir()]
                        print("EMPTY-PY", box.name, sub, uid, names[:12])
    print("total_hits", hits)


if __name__ == "__main__":
    main()
