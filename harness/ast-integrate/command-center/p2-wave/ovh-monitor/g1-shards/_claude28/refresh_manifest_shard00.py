#!/usr/bin/env python3
"""Shard-00 helper: refresh sha256/bytes rows in a unit's UNIT-ARTIFACT-MANIFEST.json.

Usage: python refresh_manifest_shard00.py <UNIT-ID> [rel/path ...]
With no paths given, refreshes every row of that unit whose file exists on disk.
Never adds or deletes rows; only updates sha256/bytes/present of existing rows.
sha256 uses the same CRLF->LF normalization as _measure_one_delivered.py.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    uid = sys.argv[1]
    only = {p.replace("\\", "/") for p in sys.argv[2:]}
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    changed = 0
    for row in man.get("artifacts") or []:
        if not isinstance(row, dict) or row.get("unit_id") != uid:
            continue
        rel = str(row.get("path") or "").replace("\\", "/")
        if only and rel not in only:
            continue
        f = REPO / rel
        if not f.is_file():
            print(f"SKIP missing {rel}")
            continue
        sha, n = digest(f)
        if row.get("sha256") != sha or row.get("bytes") not in (None, n) or row.get("present") is not True:
            row["sha256"] = sha
            if "bytes" in row:
                row["bytes"] = n
            row["present"] = True
            changed += 1
            print(f"UPDATED {rel} sha256={sha} bytes={n}")
        else:
            print(f"OK {rel}")
    if changed:
        man_path.write_text(json.dumps(man, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"rows-updated={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
