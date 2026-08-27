#!/usr/bin/env python3
"""Non-interactive backfill render of ONE subagent transcript, then EXIT.

Wraps the vendored ``monitorcore.agent_tail`` (``header`` / ``read_tail_entries`` / ``render``)
and exits, so a transcript can be dumped headlessly — the live tail
(``python -m monitorcore.agent_tail <jsonl>``) never self-exits.

``monitorcore`` is vendored inside the SIBLING ``workflow-monitor`` skill, so that dir is put
on ``sys.path``. This resolves both in-repo (``skills/workflow-monitor``) and deployed
(``~/.agents/skills/workflow-monitor``), because ``sync-skills.ps1`` lays the two skills out
as siblings in either location.

Usage:  python tail_once.py <path-to-agent-*.jsonl> [N]   (N = events, default 8)
"""

from __future__ import annotations

import os
import sys

# The sibling workflow-monitor skill vendors ``monitorcore`` — put it on sys.path.
_SKILLS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WFMON = os.path.join(_SKILLS_ROOT, "workflow-monitor")
if _WFMON not in sys.path:
    sys.path.insert(0, _WFMON)

from monitorcore import agent_tail  # noqa: E402  (intentional: after sys.path setup)


def main() -> int:
    # Reconfigure stdout to UTF-8 (errors=replace) + enable VT, exactly like the live tailer,
    # so the box-drawing header does not raise UnicodeEncodeError on a cp1252 console / pipe.
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
