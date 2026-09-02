#!/usr/bin/env python3
"""CNF-0157 fixture hook: write a side-effect file when actually executed."""
from __future__ import annotations

import os
from pathlib import Path

target = os.environ.get("CNF0157_SIDE_EFFECT")
if not target:
    raise SystemExit("CNF0157_SIDE_EFFECT is required; refusing silent no-op")
path = Path(target)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("hook-fired\n", encoding="utf-8", newline="\n")
