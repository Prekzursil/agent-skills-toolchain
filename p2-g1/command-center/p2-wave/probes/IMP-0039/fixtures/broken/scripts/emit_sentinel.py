#!/usr/bin/env python3
"""Hook payload for the IMP-0039 healthy/broken fixtures.

Writes the hook-fired sentinel line the probe checks for: HOOK_FIRED:<nonce>:<id>.
The nonce comes from the probe env, so a stale sentinel can never satisfy a
later run.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

nonce = os.environ.get("HOOK_FIRE_NONCE", "")
hook_id = os.environ.get("HOOK_FIRE_ID", "")
sentinel = os.environ.get("HOOK_FIRE_SENTINEL_PATH", "")

if sentinel:
    p = Path(sentinel)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(f"HOOK_FIRED:{nonce}:{hook_id}\n")
print(f"hook-emitted {hook_id}")
sys.exit(0)
