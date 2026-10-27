#!/usr/bin/env python3
"""TST-0088 victim: streams a plausible artifact then holds forever.

Writes a COMPLETE, parseable, SUCCESS-looking JSON artifact (a partial
write that already looks done), flushes + fsyncs, prints READY, then
sleeps until killed. The kill lands after the parseable prefix exists,
exactly the receipt's injected fault."""
import json
import sys
import time
from pathlib import Path

dest = Path(sys.argv[1])
rows = [{"n": i, "data": "x" * 48} for i in range(48)]
doc = {"unit_id": "VICTIM-0088", "title": "streamed artifact", "state": "SUCCESS",
       "rows": rows, "notes": "plausible partial - complete JSON, no sentinel"}
dest.write_text(json.dumps(doc, indent=1), encoding="utf-8")
import os
fd = os.open(dest, os.O_RDWR)
os.fsync(fd)
os.close(fd)
print("READY", flush=True)
time.sleep(600)
