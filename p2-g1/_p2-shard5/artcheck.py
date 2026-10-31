#!/usr/bin/env python3
"""shard-5 helper: hash an artifact (CRLF-normalized, gate convention) or
check that the per-unit manifest row matches the live artifact.

Usage:
  python _p2-shard5/artcheck.py hash <repo-relative-path>
  python _p2-shard5/artcheck.py manifest <UNIT-ID>
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def digest_norm(path: Path):
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), ("CRLF" if b"\r\n" in raw else "LF")


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: artcheck.py hash <path> | manifest <UID>")
        return 2
    mode = sys.argv[1]
    if mode == "hash":
        p = REPO / sys.argv[2]
        if not p.is_file():
            print("FAILED:artcheck missing", sys.argv[2])
            return 1
        sha, n, eol = digest_norm(p)
        print(f"{sys.argv[2]} eol={eol} bytes={n} sha256={sha}")
        return 0
    if mode == "manifest":
        uid = sys.argv[2]
        doc = json.loads((REPO / "command-center/receipts" / (uid + ".json")).read_text(encoding="utf-8"))
        art_rel = None
        for row in doc.get("artifacts") or []:
            if isinstance(row, dict) and row.get("role") == "primary":
                art_rel = row.get("path")
        if not art_rel:
            print("FAILED:artcheck no primary artifact row in receipt", uid)
            return 1
        live_sha, _, _ = digest_norm(REPO / art_rel)
        man = json.loads((REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
        for row in man.get("artifacts") or []:
            if isinstance(row, dict) and row.get("unit_id") == uid \
               and str(row.get("path") or "").replace("\\", "/") == art_rel:
                ok = row.get("sha256") == live_sha and row.get("present") is True
                print(f"{uid} manifest-row match={ok} sha256={live_sha[:16]}...")
                print("SUCCESS:artcheck" if ok else "FAILED:artcheck sha mismatch")
                return 0 if ok else 1
        print("FAILED:artcheck no manifest row for", art_rel)
        return 1
    print("unknown mode")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
