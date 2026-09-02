#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

WAVE = Path(__file__).resolve().parents[1]
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "class-probe-missing.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]


def main() -> None:
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        print("=" * 70)
        print(uid)
        for p in sorted(pdir.glob("probe*.py")):
            text = p.read_text(encoding="utf-8", errors="replace")
            print(f"--- {p.name} {len(text)} bytes ---")
            # print first 40 lines
            lines = text.splitlines()
            for i, ln in enumerate(lines[:45], 1):
                print(f"{i:3}|{ln}")
            if len(lines) > 45:
                print(f"... {len(lines)-45} more lines")


if __name__ == "__main__":
    main()
