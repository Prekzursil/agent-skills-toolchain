#!/usr/bin/env python3
"""Child argv echo: print each received argument's exact bytes as JSON.

Used by TST-0191 to prove argv-array spawning preserves argument bytes.
Output is ASCII-safe JSON: one record per argument with the byte length and
the hex of ``os.fsencode(arg)``.
"""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    records = []
    for arg in sys.argv[1:]:
        raw = os.fsencode(arg)
        records.append({"n": len(raw), "hex": raw.hex()})
    sys.stdout.write(json.dumps(records, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
