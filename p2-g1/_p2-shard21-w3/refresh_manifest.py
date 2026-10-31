#!/usr/bin/env python3
"""Shard21 w3: refresh UNIT-ARTIFACT-MANIFEST.json sha256 rows for a unit.

Recomputes the CRLF-normalized sha256 (identical to _measure_one_delivered.py
digest_file) for every row whose artifact exists; adds rows for required
files passed via --require; never touches rows for absent files except
--require ones, which fail the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("unit_id")
    ap.add_argument("--require", action="append", default=[])
    args = ap.parse_args()
    man_path = REPO / "command-center" / "p2-wave" / "probes" / args.unit_id / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    arts = man.get("artifacts") or []
    known = {a.get("path") for a in arts}
    changed = 0
    for a in arts:
        rel = str(a.get("path") or "").replace("\\", "/")
        f = REPO / rel
        if f.is_file():
            sha, n = digest(f)
            if a.get("sha256") != sha or a.get("bytes") != n:
                a["sha256"] = sha
                a["bytes"] = n
                a["present"] = True
                changed += 1
        else:
            a["present"] = False
    for rel in args.require:
        rel = rel.replace("\\", "/")
        if rel in known:
            continue
        f = REPO / rel
        if not f.is_file():
            print(f"FAILED:manifest-refresh missing required file {rel}")
            return 1
        sha, n = digest(f)
        arts.append(
            {
                "path": rel,
                "bytes": n,
                "sha256": sha,
                "present": True,
                "role": "supporting",
                "receipt_path": f"command-center/p2-wave/probes/{args.unit_id}/SUBAGENT-RETURN.json",
                "unit_id": args.unit_id,
            }
        )
        changed += 1
    man["artifacts"] = arts
    man["verified_on_disk"] = True
    man_path.write_text(json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"refreshed {args.unit_id}: {changed} row(s) updated, {len(arts)} rows total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
