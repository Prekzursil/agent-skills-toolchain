#!/usr/bin/env python3
"""Fixture stage: write a non-empty artifact under WFA0124_OUT."""
from __future__ import annotations

import json
import os
from pathlib import Path

out_dir = Path(os.environ["WFA0124_OUT"])
out_dir.mkdir(parents=True, exist_ok=True)
dest = out_dir / "result.json"
dest.write_text(
    json.dumps({"ok": True, "probe": "WFA-0124"}, indent=2) + "\n",
    encoding="utf-8",
)
print(f"wrote {dest}")
