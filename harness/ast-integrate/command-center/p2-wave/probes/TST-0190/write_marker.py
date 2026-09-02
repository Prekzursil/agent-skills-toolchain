#!/usr/bin/env python3
"""Child: write a payload at argv dest. Exit 2 if dest cannot be created."""
from __future__ import annotations

import sys
from pathlib import Path

dest = Path(sys.argv[1])
payload = sys.argv[2] if len(sys.argv) > 2 else "TST-0190-clone-payload\n"
try:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(payload, encoding='utf-8')
except OSError as exc:
    print(f'WRITE_FAIL {type(exc).__name__}: {exc}', file=sys.stderr)
    raise SystemExit(2)
print(str(dest))
