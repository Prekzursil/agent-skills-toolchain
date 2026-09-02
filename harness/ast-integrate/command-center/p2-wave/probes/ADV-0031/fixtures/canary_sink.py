#!/usr/bin/env python3
"""Record argv only. Never evaluate the workflow-parameter payload as a command."""
from __future__ import annotations

import json
import sys
from pathlib import Path

record = Path(sys.argv[1])
record.parent.mkdir(parents=True, exist_ok=True)
record.write_text(
    json.dumps({"argv": sys.argv, "param": sys.argv[2] if len(sys.argv) > 2 else ""}, sort_keys=True)
    + "\n",
    encoding="utf-8",
)
