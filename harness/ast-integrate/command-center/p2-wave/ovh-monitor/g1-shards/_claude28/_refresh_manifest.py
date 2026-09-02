#!/usr/bin/env python3
"""Shard-03 helper: refresh UNIT-ARTIFACT-MANIFEST.json sha256 rows.

Usage: python _refresh_manifest.py <UNIT-ID> <repo-rel-path> [...]
Recomputes CRLF-normalized sha256/bytes for the given rows.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]


def main() -> int:
    unit = sys.argv[1]
    targets = set(sys.argv[2:])
    mp = REPO / "command-center" / "p2-wave" / "probes" / unit / "UNIT-ARTIFACT-MANIFEST.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    seen = set()
    for a in m.get("artifacts", []):
        if a.get("path") in targets:
            raw = (REPO / a["path"]).read_bytes().replace(b"\r\n", b"\n")
            a["sha256"] = hashlib.sha256(raw).hexdigest()
            a["bytes"] = len(raw)
            seen.add(a["path"])
            print(f"updated {a['path']} {a['sha256'][:12]} {a['bytes']}")
    mp.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8", newline="\n")
    missing = targets - seen
    if missing:
        print(f"NOT-IN-MANIFEST: {sorted(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
