#!/usr/bin/env python3
"""Regression oracle: an empty or BLOCKED artifact must not count as delivered.

FAIL on the pre-fix existence-only detector. PASS on the post-fix predicate.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
root = Path(os.environ["SUBJECT_ROOT"])
tmp = Path(os.environ["ORACLE_TMP"])
sys.path.insert(0, str(root))
from detector import is_delivered  # noqa: E402

empty = tmp / "empty.json"
empty.write_text("", encoding="utf-8")
blocked = tmp / "blocked.json"
blocked.write_text(json.dumps({"state": "BLOCKED"}, sort_keys=True), encoding="utf-8")
good = tmp / "good.json"
good.write_text(
    json.dumps({"state": "SUCCESS", "sentinel": "ok"}, sort_keys=True),
    encoding="utf-8",
)

if is_delivered(empty) or is_delivered(blocked) or not is_delivered(good):
    sys.exit(1)
sys.exit(0)
