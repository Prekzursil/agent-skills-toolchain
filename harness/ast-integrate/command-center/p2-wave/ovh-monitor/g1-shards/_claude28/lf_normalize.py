#!/usr/bin/env python3
"""Rewrite files with CRLF line endings to LF (bytes-level, idempotent)."""
import sys
from pathlib import Path

for arg in sys.argv[1:]:
    p = Path(arg)
    raw = p.read_bytes()
    fixed = raw.replace(b"\r\n", b"\n")
    if fixed != raw:
        p.write_bytes(fixed)
        print(f"LF-normalized {p}")
    else:
        print(f"already-LF {p}")
