"""What argv does the manifest hand each check? The dispatcher passes it; a probe that
omits it runs a DIFFERENT program from the one the harness runs."""

from __future__ import annotations

import json
import os
import pathlib

LIVE = pathlib.Path(os.path.expanduser("~/.claude/hooks"))
man = json.loads((LIVE / "_dispatch" / "manifest.json").read_text(encoding="utf-8"))
n = 0
with_args = 0
for ev, blob in (man.get("events") or {}).items():
    for chk in (blob or {}).get("checks") or []:
        n += 1
        args = chk.get("args") or []
        if args:
            with_args += 1
            print(f"{ev:<13} {str(chk.get('name')):<30} args={args}")
print()
print(f"checks={n}  with non-empty args={with_args}")
if n < 20:
    raise SystemExit(f"FAILED:args blind reader, {n} checks")
print("SUCCESS:args")
