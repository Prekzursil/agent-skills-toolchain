#!/usr/bin/env python3
"""Update per-unit UNIT-ARTIFACT-MANIFEST sha256/bytes from the live catalog artifact."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sync(uid: str) -> int:
    unit = BY[uid]
    rel = str(unit["output_path"]).replace("\\", "/")
    art = REPO / rel
    if not art.is_file():
        print("missing artifact", rel)
        return 1
    sha, size = digest(art)
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    hit = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("unit_id") not in {None, uid}:
            continue
        path = str(row.get("path") or "").replace("\\", "/")
        if path == rel or row.get("role") == "primary":
            row["path"] = rel
            row["sha256"] = sha
            row["bytes"] = size
            row["present"] = True
            row["unit_id"] = uid
            hit = True
    if not hit:
        rows.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
                "unit_id": uid,
                "role": "primary",
            }
        )
        man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(uid, rel, size, sha)
    return 0


def main() -> int:
    ids = sys.argv[1:]
    rc = 0
    for uid in ids:
        rc |= sync(uid)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
