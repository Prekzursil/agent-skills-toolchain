#!/usr/bin/env python3
"""Fixture stage: write a non-empty artifact under CNF0077_OUT."""
from __future__ import annotations

import json
import os
from pathlib import Path

out_dir = Path(os.environ["CNF0077_OUT"])
out_dir.mkdir(parents=True, exist_ok=True)
dest = out_dir / "result.json"
dest.write_text(json.dumps({"ok": True, "probe": "CNF-0077"}, indent=2) + "\n", encoding="utf-8")
print(f"wrote {dest}")
