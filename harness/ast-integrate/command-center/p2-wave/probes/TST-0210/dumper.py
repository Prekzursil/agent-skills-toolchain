"""Print JSON list of child environment KEYS only. Never print values."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

keys = sorted(os.environ.keys())
payload = json.dumps(keys)
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(payload + "\n", encoding="utf-8")
sys.stdout.write(payload)
sys.stdout.write("\n")
