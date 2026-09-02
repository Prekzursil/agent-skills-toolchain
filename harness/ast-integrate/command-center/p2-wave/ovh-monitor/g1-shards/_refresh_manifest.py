#!/usr/bin/env python3
"""Update per-unit UNIT-ARTIFACT-MANIFEST.json sha256 to match live output_path."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh(uid: str) -> None:
    unit = BY[uid]
    out_rel = str(unit["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    sha, size = digest(out)
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = man.get("artifacts") or []
    found = False
    for a in rows:
        if not isinstance(a, dict):
            continue
        if a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == out_rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
            found = True
    if not found:
        rows.append(
            {
                "unit_id": uid,
                "path": out_rel,
                "sha256": sha,
                "bytes": size,
                "present": True,
            }
        )
        man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{uid} sha={sha[:16]} bytes={size}")


def main() -> None:
    ids = sys.argv[1:]
    for uid in ids:
        refresh(uid)


if __name__ == "__main__":
    main()
