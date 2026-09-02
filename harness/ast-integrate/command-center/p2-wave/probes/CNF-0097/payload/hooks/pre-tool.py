#!/usr/bin/env python3
"""Declared PreToolUse hook shipped inside the published artifact."""
from __future__ import annotations

import json
import os
from pathlib import Path

prefix = os.environ.get("HARNESS_PREFIX")
if prefix:
    dest = Path(prefix) / "hook-side-effect.json"
else:
    dest = Path(__file__).resolve().parents[1] / "hook-side-effect.json"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(
    json.dumps({"fired": True, "hook": "pre-tool"}, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"hook-fired {dest.as_posix()}")
