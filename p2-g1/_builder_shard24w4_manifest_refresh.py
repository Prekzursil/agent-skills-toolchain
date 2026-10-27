#!/usr/bin/env python3
"""Refresh stale UNIT-ARTIFACT-MANIFEST rows to live CRLF-normalized hashes.

Scope: shard24-w4 units EXCEPT BLD-0037 (its write_receipts.py rewrites its
own manifest). Touches ONLY the per-unit manifest rows whose live bytes
differ from the recorded sha256. Never touches artifacts, probes,
SUBAGENT-RETURN.json, receipts or reviewer closures.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "AUD-0096", "BLD-0001", "BLD-0002", "BLD-0010", "BLD-0016", "BLD-0023",
    "BLD-0024", "BLD-0027", "BLD-0028", "BLD-0049", "BLD-0058",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    failures = []
    for uid in UNITS:
        mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        man = json.loads(mp.read_text(encoding="utf-8"))
        changed = []
        for a in man.get("artifacts", []):
            f = REPO / a["path"]
            if not f.is_file():
                failures.append(f"{uid} {a['path']} ABSENT")
                continue
            sha, n = digest(f)
            if sha != a.get("sha256") or n != a.get("bytes"):
                changed.append((a["path"], a.get("sha256", "")[:8], sha[:8]))
                a["sha256"] = sha
                a["bytes"] = n
                a["present"] = True
        if changed:
            text = json.dumps(man, indent=1, sort_keys=True) + "\n"
            mp.write_text(text, encoding="utf-8", newline="\n")
        print(f"{uid}: rows={len(man.get('artifacts', []))} refreshed={len(changed)}")
        for c in changed:
            print(f"   {c[0]} {c[1]}.. -> {c[2]}..")
    if failures:
        print("FAILED:manifest-refresh " + "; ".join(failures))
        return 1
    print("SUCCESS:shard24w4-manifest-refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
