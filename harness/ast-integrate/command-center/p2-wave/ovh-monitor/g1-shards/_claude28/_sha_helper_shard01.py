#!/usr/bin/env python3
"""shard-01 scratch: print normalized sha256 + byte count for files (CRLF->LF)."""
import hashlib
import sys
from pathlib import Path

for arg in sys.argv[1:]:
    raw = Path(arg).read_bytes().replace(b"\r\n", b"\n")
    print(f"{hashlib.sha256(raw).hexdigest()} {len(raw)} {arg}")
