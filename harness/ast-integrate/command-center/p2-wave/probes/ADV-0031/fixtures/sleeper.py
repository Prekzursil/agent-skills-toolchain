#!/usr/bin/env python3
"""Hold the process table long enough for /proc cmdline capture."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

record = Path(sys.argv[1])
record.parent.mkdir(parents=True, exist_ok=True)
record.write_text(
    json.dumps(
        {
            "argv": sys.argv,
            "param": sys.argv[2] if len(sys.argv) > 2 else "",
            "pid": os.getpid(),
            "ppid": os.getppid(),
        },
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
time.sleep(float(os.environ.get("ADV0031_SLEEP", "1.6")))
