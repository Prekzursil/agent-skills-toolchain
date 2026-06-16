#!/usr/bin/env python3
"""Non-interactive backfill render of ONE subagent transcript, then EXIT.

`agent_tail.py` is a live poll loop (Ctrl-C to quit) — great for a terminal,
useless for a script or an agent's bash tool. This wraps the SAME rendering
code (`agent_tail.header` / `read_tail_entries` / `render`) and exits, so a
transcript can be dumped headlessly.

Usage:  python tail_once.py <path-to-agent-*.jsonl> [N]   (N = events, default 8)
"""
from __future__ import annotations

import os
import sys

# Put the repo root (three dirs up from this skill file) on sys.path so the
# stdlib-only agent_tail module imports regardless of the current directory.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import agent_tail  # noqa: E402  (intentional: after sys.path setup)


def main() -> int:
    # Reconfigure stdout to UTF-8 (errors=replace) + enable VT, exactly like the
    # real scripts' main() does. Without this, printing the box-drawing header on a
    # cp1252 console / pipe raises UnicodeEncodeError (PYTHONUTF8=1 would also fix it,
    # but the helper must not depend on the caller setting that).
    agent_tail._enable_vt()
    if len(sys.argv) < 2:
        print("usage: python tail_once.py <agent-*.jsonl> [N]")
        return 2
    path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    if not os.path.exists(path):
        print(f"not found: {path}")
        return 1
    agent_tail.header(path, 100)
    print("-- last %d events --" % n)
    for entry in agent_tail.read_tail_entries(path, n):
        for line in agent_tail.render(entry, 100):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
