#!/usr/bin/env python3
"""Refresh UNIT-ARTIFACT-MANIFEST sha256 rows (CRLF->LF). Not unit_manifest.py --write."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh_manifest(uid: str, rels: list[str]) -> None:
    man_path = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    want = {r.replace("\\", "/") for r in rels}
    artifacts = list(man.get("artifacts") or [])
    have = {str(row.get("path") or "").replace("\\", "/") for row in artifacts}
    updated = []
    for p in sorted(want - have):
        live = REPO / p
        row = {
            "path": p,
            "unit_id": uid,
            "present": live.is_file(),
            "role": "supporting",
        }
        if live.is_file():
            sha, n = digest_file(live)
            row["sha256"] = sha
            row["bytes"] = n
        artifacts.append(row)
        updated.append(f"{p}:ADDED")
    for row in artifacts:
        p = str(row.get("path") or "").replace("\\", "/")
        if p in want:
            live = REPO / p
            if not live.is_file():
                row["present"] = False
                updated.append(f"{p}:MISSING")
                continue
            sha, n = digest_file(live)
            row["sha256"] = sha
            row["bytes"] = n
            row["present"] = True
            if row.get("unit_id") in (None, ""):
                row["unit_id"] = uid
            updated.append(f"{p}:{sha[:12]}")
    man["artifacts"] = artifacts
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    print("manifest", uid, *updated, sep="\n  ")


def dump_keys(rel: str, max_depth: int = 1) -> None:
    p = REPO / rel
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print(rel, "NOT_DICT", type(doc).__name__)
        return
    print(rel, "TOP", sorted(doc.keys()))
    for k in ("report", "receipt", "body", "payload", "result", "controls", "tests", "denials"):
        v = doc.get(k)
        if isinstance(v, dict):
            print(f"  .{k}", sorted(v.keys())[:40])
        elif isinstance(v, list):
            print(f"  .{k} list n={len(v)} sample={type(v[0]).__name__ if v else None}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "refresh":
        refresh_manifest(sys.argv[2], sys.argv[3:])
    elif cmd == "keys":
        for rel in sys.argv[2:]:
            dump_keys(rel)
    else:
        raise SystemExit("usage: refresh UID rel... | keys rel...")
