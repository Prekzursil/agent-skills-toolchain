#!/usr/bin/env python3
# RES-0009 logging hook: stores the VERBATIM stdin JSON bytes to the path in
# RES0009_LOG, then exits 0. Used to prove the payload round-trips verbatim
# (field hook_event_name present, sha256 recorded).
import hashlib
import json
import os
import sys

if __name__ == "__main__":
    raw = sys.stdin.buffer.read()
    dest = os.environ["RES0009_LOG"]
    doc = {
        "stdin_sha256": hashlib.sha256(raw).hexdigest(),
        "verbatim": json.loads(raw.decode("utf-8")),
    }
    with open(dest, "w", encoding="utf-8", newline=chr(10)) as f:
        json.dump(doc, f, indent=1)
    print(json.dumps({"ok": True, "event": doc["verbatim"].get("hook_event_name")}))
    sys.exit(0)
