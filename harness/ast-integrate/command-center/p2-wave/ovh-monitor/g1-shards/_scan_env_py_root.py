#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

IDS = [
    "ADV-0139",
    "ARC-0005",
    "ARC-0004",
    "ARC-0049",
    "ARC-0089",
    "AUD-0074",
    "BLD-0036",
    "CNF-0045",
    "CNF-0101",
    "IMP-0025",
    "IMP-0036",
    "RES-0010",
    "RES-0015",
    "RES-0102",
    "RES-0177",
    "TST-0072",
    "WFA-0018",
    "WFA-0039",
    "WFA-0044",
    "WFA-0045",
    "WFA-0133",
    "WFA-0141",
]
PROBES = Path(__file__).resolve().parents[2] / "probes"


def main() -> None:
    for uid in IDS:
        d = PROBES / uid
        print("====", uid)
        fix = d / "fixtures"
        if fix.is_dir():
            n = sum(1 for p in fix.rglob("*") if p.is_file())
            print("  fixtures files", n)
            kids = [p.name for p in fix.iterdir()]
            print("  fixtures top", kids[:20])
        else:
            print("  NO fixtures dir")
        for p in sorted(d.glob("*.py")):
            txt = p.read_text(encoding="utf-8", errors="replace")
            if "/root" not in txt:
                continue
            print(" ", p.name)
            for i, line in enumerate(txt.splitlines(), 1):
                if "/root" in line:
                    print(f"    {i}: {line.rstrip()[:220]}")


if __name__ == "__main__":
    main()
