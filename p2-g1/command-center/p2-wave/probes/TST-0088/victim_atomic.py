#!/usr/bin/env python3
"""TST-0088 atomic victim: writes to a tmp file then holds before rename.

Under the atomic-write fix the partial lands ONLY in the tmp path; the
kill before the rename leaves the destination invisible. Prints READY
when the tmp file exists; killed while holding."""
import json
import os
import sys
import time
from pathlib import Path

dest = Path(sys.argv[1])
tmp = Path(str(dest) + ".tmp")
rows = [{"n": i, "data": "y" * 48} for i in range(48)]
doc = {"unit_id": "VICTIM-0088", "title": "streamed artifact", "state": "SUCCESS",
       "rows": rows, "notes": "tmp-side partial, destination not yet published"}
tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
fd = os.open(tmp, os.O_RDWR)
os.fsync(fd)
os.close(fd)
print("READY", flush=True)
time.sleep(600)
