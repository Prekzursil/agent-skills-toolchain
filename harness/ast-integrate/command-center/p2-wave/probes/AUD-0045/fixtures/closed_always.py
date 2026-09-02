#!/usr/bin/env python3
"""Control fixture: exits 1 on empty and on known-bad, prints a measured count."""
from __future__ import annotations

import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "empty"
print(f"FAILED:closed-control mode={mode} count=1")
raise SystemExit(1)
