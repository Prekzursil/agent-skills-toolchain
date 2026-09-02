#!/usr/bin/env python3
"""Verify each mechanism excerpt exists at the cited cache line."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mechanisms import MECHANISMS  # noqa: E402

CACHE = HERE / "cache"


def main() -> int:
    bad = []
    for m in MECHANISMS:
        path = CACHE / m["cache"]
        if not path.is_file():
            bad.append((m, "missing-cache"))
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        idx = int(m["line"]) - 1
        excerpt = m["excerpt"]
        if idx < 0 or idx >= len(lines):
            bad.append((m, f"line-oob n={len(lines)}"))
            continue
        if excerpt not in lines[idx]:
            window = "\n".join(f"{i+1}:{lines[i]}" for i in range(max(0, idx-2), min(len(lines), idx+3)))
            bad.append((m, f"excerpt-miss\n{window}"))
    if bad:
        for m, why in bad:
            print(f"BAD {m['runtime']}/{m['mechanism']} {m['cache']}:{m['line']} {why}")
        print(f"FAILED {len(bad)}/{len(MECHANISMS)}")
        return 1
    print(f"OK {len(MECHANISMS)} excerpts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
