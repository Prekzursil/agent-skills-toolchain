"""Read the LIVE manifest via events[ev]["checks"] -- the collection, not the dict above it.

`manifest["events"][ev]` is a dict {settings_matcher, settings_timeout, checks}; iterating it
yields three KEY NAMES and len() reports 3 for every event on both trees. That is the false
parity that four successive probes in this program agreed on and all four were wrong.
"""

from __future__ import annotations

import json
import os
import pathlib

LIVE = pathlib.Path(os.path.expanduser("~/.claude/hooks"))
man = json.loads((LIVE / "_dispatch" / "manifest.json").read_text(encoding="utf-8"))
events = man.get("events") or {}

total = 0
print("{:<13} {:<32} {:<26} {:>8}".format("event", "check", "matcher", "timeout"))
print("-" * 84)
for ev, blob in events.items():
    for chk in (blob or {}).get("checks") or []:
        total += 1
        print(
            "{:<13} {:<32} {:<26} {:>8}".format(
                ev,
                str(chk.get("name") or chk.get("script")),
                str(chk.get("matcher")),
                str(chk.get("timeout")),
            )
        )

# Fail closed on an implausible count: a shape change must be loud, not report parity.
print()
print(f"events={len(events)}  checks={total}")
if total < 20:
    raise SystemExit(
        f"FAILED:matchers implausible check count {total} -- reader is blind"
    )
print("SUCCESS:matchers")
