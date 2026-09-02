#!/usr/bin/env python3
"""Emit a per-trigger nonce. Presence of this file is not a fire signal."""
from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    nonce = os.environ.get("HOOK_FIRE_NONCE", "")
    dest = os.environ.get("HOOK_FIRE_SENTINEL_PATH", "")
    hook_id = os.environ.get("HOOK_FIRE_ID", "hook.pre-tool")
    if not nonce or not dest:
        return 2
    path = Path(dest)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"HOOK_FIRED:{nonce}:{hook_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
