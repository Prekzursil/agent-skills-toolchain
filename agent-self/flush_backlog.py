#!/usr/bin/env python3
"""Flush stale bm-spool records using the FIXED flusher (adds --folder).
Run from agent-self/ so `import harness.modules` resolves."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from harness.modules import _flush_spool_to_vault  # noqa: E402

SPOOL = pathlib.Path(r"C:\Users\Prekzursil\.agents\state\harness\bm-spool")
ok, fail = [], []
for path in sorted(SPOOL.glob("*.json")):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("flushed"):
        continue
    if _flush_spool_to_vault(payload):
        payload["flushed"] = True
        path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        ok.append(path.name)
    else:
        fail.append(path.name)

print(f"flushed={len(ok)} failed={len(fail)}")
if ok:
    print("  ok:", ", ".join(ok))
if fail:
    print("  FAILED:", ", ".join(fail))
print("SUCCESS:bm-spool-backlog-flush" if not fail else "FAILED:bm-spool-backlog-flush")
sys.exit(0 if not fail else 1)
