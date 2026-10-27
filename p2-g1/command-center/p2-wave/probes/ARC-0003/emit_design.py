#!/usr/bin/env python3
"""Emit the A1 (config-first minimal) DESIGN fragment.

Dependency fixture materialized 2026-10-24 by the p2-g1 shard-1 builder:
ARC-0047's emit cites this file for the A1 unlisted-file contract; the
original probes/ARC-0003/ tree was absent on this worktree. The contract
line below is the load-bearing text the downstream anchor resolves.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path("command-center/phase3/A1/DESIGN.json")

DESIGN = {
    "unit_id": "ARC-0003",
    "architecture_id": "A1",
    "architecture_class": "config-first-minimal",
    "loader_contract": {
        "manifest_authority": "MANIFEST.json lists every loadable capability file.",
        "unlisted_file": "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
    },
    "title": "A1 (config-first minimal) design fragment",
}


def main() -> int:
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(DESIGN, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
