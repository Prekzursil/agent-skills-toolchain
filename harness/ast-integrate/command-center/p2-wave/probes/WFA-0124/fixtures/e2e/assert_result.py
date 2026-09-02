#!/usr/bin/env python3
"""Flagship e2e: postcondition on the artifact the smoke stage produced."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

out_dir = Path(os.environ["WFA0124_OUT"])
dest = out_dir / "result.json"
if not dest.is_file() or dest.stat().st_size < 16:
    print("FAILED:e2e artifact missing or too small", dest)
    sys.exit(1)
try:
    doc = json.loads(dest.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    print("FAILED:e2e unparseable", exc)
    sys.exit(1)
if doc.get("ok") is not True:
    print("FAILED:e2e postcondition ok!=true", doc)
    sys.exit(1)
print("SUCCESS:e2e postcondition on result.json")
