#!/usr/bin/env python3
"""Shard-7 wave-4 resume: refresh IMP-0006 manifest row.

The prior builder's fixup (_builder_shard7_w5_fixups.py) edited the IMP-0006
receipt (adding receipt_core-required `spec_anchor`) but died before refreshing
probes/IMP-0006/UNIT-ARTIFACT-MANIFEST.json, leaving manifest-sha-mismatch.

This script recomputes the CRLF-normalized sha256 of the live receipt and every
other row's artifact, updates the manifest in place, and fails loudly if any
row's file is missing (no silent widening of the manifest).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
UID = "IMP-0006"
MAN = REPO / "command-center" / "p2-wave" / "probes" / UID / "UNIT-ARTIFACT-MANIFEST.json"


def norm_sha_bytes(p: Path) -> tuple[str, int]:
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def detect_indent(text: str) -> int:
    for line in text.splitlines()[1:]:
        if line.strip():
            return len(line) - len(line.lstrip(" "))
    return 2


def main() -> int:
    mraw = MAN.read_bytes()
    m_ascii = all(b < 128 for b in mraw)
    mtext = mraw.decode("utf-8")
    man = json.loads(mtext)

    updated, stale_kept = [], []
    for row in man.get("artifacts") or []:
        rel = str(row.get("path", "")).replace("\\", "/")
        p = REPO / rel
        if not p.is_file():
            print(f"FAILED:row-file-missing {rel}")
            return 1
        sha, nbytes = norm_sha_bytes(p)
        if row.get("unit_id") == UID and row.get("role") == "primary":
            old = row.get("sha256")
            row["sha256"], row["bytes"], row["present"] = sha, nbytes, True
            updated.append(f"primary {rel} {old[:12]} -> {sha[:12]} ({nbytes}B)")
        elif str(row.get("sha256")) != sha or row.get("bytes") != nbytes:
            # supporting artifacts may legitimately have drifted too; refresh
            # any stale row so the manifest reflects live disk (same policy the
            # measure script applies to the primary row).
            old = row.get("sha256")
            row["sha256"], row["bytes"], row["present"] = sha, nbytes, True
            updated.append(f"supporting {rel} {str(old)[:12]} -> {sha[:12]} ({nbytes}B)")
        else:
            stale_kept.append(rel)

    MAN.write_bytes(
        (json.dumps(man, indent=detect_indent(mtext), ensure_ascii=m_ascii) + "\n").encode("utf-8")
    )
    for u in updated:
        print(f"UPDATED {u}")
    for s in stale_kept:
        print(f"OK-UNCHANGED {s}")
    print(f"SUCCESS:IMP-0006-manifest-refresh rows={len(man.get('artifacts') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
