#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

WAVE = Path(__file__).resolve().parents[2]
ROOT = WAVE / "ovh-monitor" / "error-pull"
UIDS = [
    "ADV-0068", "ADV-0090", "ADV-0113",
    "IMP-0268", "TST-0135", "TST-0164", "IMP-0142", "IMP-0165",
    "IMP-0231", "TST-0052", "TST-0316", "WFA-0017",
]


def walk_limited(root: Path) -> None:
    if not root.is_dir():
        print("missing", root)
        return
    print("root", root)
    for box in sorted(root.iterdir()):
        if not box.is_dir():
            continue
        # typical layouts
        candidates = [
            box / "command-center" / "p2-wave" / "probes",
            box / "tree" / "command-center" / "p2-wave" / "probes",
            box / "delta" / "command-center" / "p2-wave" / "probes",
            box / "extracted-delta" / "par-c" / "probes",
            box / "extracted-delta" / "probes",
        ]
        # also one-level children named extracted-*
        if box.name.startswith("extracted") or (box / "extracted-delta").is_dir():
            ed = box / "extracted-delta"
            if ed.is_dir():
                for child in ed.iterdir():
                    if child.is_dir():
                        candidates.append(child / "probes")
                        candidates.append(child / "command-center" / "p2-wave" / "probes")
        for probes in candidates:
            if not probes.is_dir():
                continue
            print(" probes-dir", probes)
            for uid in UIDS:
                d = probes / uid
                if not d.is_dir():
                    continue
                pys = sorted(p.name for p in d.iterdir() if p.suffix == ".py")
                print("  ", uid, pys[:20])


if __name__ == "__main__":
    walk_limited(ROOT)
    # also leftover scw
    walk_limited(WAVE / "scw-pull")
