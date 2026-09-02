#!/usr/bin/env python3
"""Copy missing probe .py files from error-pull harvest into the live probe dirs."""
from __future__ import annotations

import shutil
from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]
LIVE = WAVE / "probes"
EP = WAVE / "ovh-monitor" / "error-pull"
UIDS = [
    "ADV-0068",
    "ADV-0090",
    "ADV-0113",
    "IMP-0268",
    "TST-0135",
    "TST-0164",
    "TST-0156",
]


def probe_roots() -> list[Path]:
    roots: list[Path] = []
    for kind in ("extracted-delta", "extracted"):
        base = EP / kind
        if not base.is_dir():
            continue
        for box in sorted(base.iterdir()):
            d = box / "probes"
            if d.is_dir():
                roots.append(d)
    return roots


def main() -> None:
    roots = probe_roots()
    print("roots", len(roots))
    for uid in UIDS:
        dest = LIVE / uid
        dest.mkdir(parents=True, exist_ok=True)
        live_py = {p.name for p in dest.glob("*.py")}
        found: dict[str, Path] = {}
        for root in roots:
            srcd = root / uid
            if not srcd.is_dir():
                continue
            for p in srcd.iterdir():
                if p.is_file() and p.suffix == ".py" and p.stat().st_size > 0:
                    # prefer larger files
                    prev = found.get(p.name)
                    if prev is None or p.stat().st_size > prev.stat().st_size:
                        found[p.name] = p
        print(uid, "live_py", sorted(live_py), "harvest_py", sorted(found))
        copied = []
        for name, src in found.items():
            if name in live_py and (dest / name).stat().st_size > 0:
                continue
            shutil.copy2(src, dest / name)
            copied.append(name)
        print("  copied", copied)


if __name__ == "__main__":
    main()
