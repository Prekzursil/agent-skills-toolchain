#!/usr/bin/env python3
"""Logging hook: persist exact stdin bytes, exit 0."""
from __future__ import annotations

import os
import sys
from pathlib import Path

raw = sys.stdin.buffer.read()
dest = os.environ.get("RES0009_CAPTURE") or os.environ.get("RES0009_CAPTURE")
if dest:
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
sys.exit(0)
