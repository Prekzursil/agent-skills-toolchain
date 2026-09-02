#!/usr/bin/env python3
"""Named probe 2: typed consumer; malformed artifact must fail.

Mechanically independent of probe 1 (required-field parse, not hashing).
A file that hashes correctly can still be unreadable; this probe shows that.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from consumer import consume, consume_registered, prove_malformed_consumer  # noqa: E402
from engine import (  # noqa: E402
    OUT_REL,
    PROGRAM_MANIFEST_REL,
    WFA_MANIFEST_REL,
    program_manifest_preserved,
)

ART = REPO / OUT_REL


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:WFA-0083-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("AuditReport missing")
    live = consume(ART, "AuditReport")
    if not live.get("ok"):
        return _fail("live AuditReport unreadable", live)
    if live.get("asserted_field") != "unit_id":
        return _fail("did not assert unit_id", live)

    ctl = prove_malformed_consumer()
    if not ctl.get("ok"):
        return _fail("malformed consumer control did not fire", ctl)
    mal = ctl.get("malformed") or {}
    if mal.get("ok"):
        return _fail("malformed payload was accepted", ctl)
    if "missing-required-fields" not in str(mal.get("error") or ""):
        return _fail("malformed error did not name missing fields", ctl)
    if not (ctl.get("well_formed") or {}).get("ok"):
        return _fail("well-formed control payload was rejected", ctl)

    wfa_path = REPO / WFA_MANIFEST_REL
    if not wfa_path.is_file():
        return _fail(f"manifest missing {WFA_MANIFEST_REL}")
    man = json.loads(wfa_path.read_text(encoding="utf-8"))
    rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict)]
    mine = [a for a in rows if a.get("unit_id") == "WFA-0083" and a.get("path") == OUT_REL]
    if not mine:
        return _fail(f"no WFA-0083 row in {WFA_MANIFEST_REL}")
    for row in rows:
        rel = str(row["path"]).replace("\\", "/")
        rtype = str(row.get("record_type") or "AuditReport")
        live_path = REPO / rel
        if not live_path.is_file():
            return _fail(f"registered path absent {rel}")
        if rel == OUT_REL:
            read = consume(live_path, "AuditReport")
        else:
            read = consume_registered(live_path, rtype)
        if not read.get("ok"):
            return _fail(f"registered row unreadable {rel}", read)

    prog = program_manifest_preserved(REPO)
    if not prog.get("ok"):
        return _fail(
            f"program ARTIFACT-MANIFEST.json was overwritten or unreadable ({PROGRAM_MANIFEST_REL})",
            prog,
        )

    print(
        json.dumps(
            {
                "probe": "probe2-consumer-malformed",
                "unit_id": "WFA-0083",
                "pass": True,
                "live_ok": True,
                "malformed_rejected": True,
                "malformed_error": mal.get("error"),
                "malformed_still_hashed": bool(ctl.get("malformed_sha256")),
                "asserted_field": live.get("asserted_field"),
            },
            indent=2,
        )
    )
    print("SUCCESS:WFA-0083-probe2 consumer required-field smoke and malformed fail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
