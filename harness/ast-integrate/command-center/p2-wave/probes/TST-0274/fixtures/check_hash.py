#!/usr/bin/env python3
"""Executable check: sha256 of the planted payload (the world, not the vote)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PAYLOAD = Path(__file__).with_name("payload.txt")


def digest() -> str:
    raw = PAYLOAD.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    asserted = digest()
    expected = sys.argv[1] if len(sys.argv) > 1 else None
    ok = expected is None or expected == asserted
    print(
        json.dumps(
            {
                "predicate": "sha256(payload.txt)",
                "asserted": asserted,
                "ok": ok,
            },
            sort_keys=True,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
