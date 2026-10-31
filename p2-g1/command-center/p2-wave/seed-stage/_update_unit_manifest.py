#!/usr/bin/env python3
"""Refresh per-unit UNIT-ARTIFACT-MANIFEST.json sha256 for one unit (not global --write)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    uid = sys.argv[1]
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next(u for u in catalog["work_units"] if u.get("id") == uid)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    sha, size = digest(out)
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    found = False
    for row in rows:
        if str(row.get("path") or "").replace("\\", "/") == out_rel:
            row["sha256"] = sha
            row["bytes"] = size
            row["present"] = True
            row["unit_id"] = uid
            found = True
    if not found:
        rows.append(
            {
                "path": out_rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
                "unit_id": uid,
                "role": "primary",
            }
        )
        man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"UPDATED {uid} {out_rel} sha256={sha} bytes={size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
