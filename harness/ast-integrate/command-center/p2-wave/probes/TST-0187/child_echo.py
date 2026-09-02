#!/usr/bin/env python3
"""Child used by TST-0187: report received payload size and argv bytes.

Two independent signals the parent cannot forge from its own bookkeeping:
  (a) argv UTF-8 byte length as THIS process received it
  (b) payload length from --payload (inline) or --payload-file (file route)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def _parse(argv: list[str]) -> tuple[str | None, str | None]:
    payload = None
    source = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--payload-file" and i + 1 < len(argv):
            payload = Path(argv[i + 1]).read_text(encoding="utf-8")
            source = "file"
            i += 2
            continue
        if a == "--payload" and i + 1 < len(argv):
            payload = argv[i + 1]
            source = "argv"
            i += 2
            continue
        if a == "--stdin":
            payload = sys.stdin.read()
            source = "stdin"
            i += 1
            continue
        i += 1
    return payload, source


def main() -> int:
    payload, source = _parse(sys.argv[1:])
    if payload is None or source is None:
        print(json.dumps({"error": "no-payload"}), file=sys.stderr)
        return 2
    raw = payload.encode("utf-8")
    argv_utf8 = sum(len(a.encode("utf-8")) for a in sys.argv)
    argv_nul_joined = sum(len(a.encode("utf-8")) + 1 for a in sys.argv)
    doc = {
        "argv_count": len(sys.argv),
        "argv_nul_joined_bytes": argv_nul_joined,
        "argv_utf8_bytes": argv_utf8,
        "payload_len": len(payload),
        "payload_sha256": hashlib.sha256(raw).hexdigest(),
        "payload_utf8_bytes": len(raw),
        "pid": os.getpid(),
        "source": source,
    }
    print(json.dumps(doc, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
