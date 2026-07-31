#!/usr/bin/env python
"""note.py — agent-facing CLI to annotate the event ledger (the 'annotator' role).

The agent calls this to record the *why* the objective hooks can't see: decisions,
failures (with falsifiable preconditions + TTL semantics), goals, milestones. A milestone
that contradicts an earlier failure auto-tombstones it (--supersedes), so dead-ends are
retired, not re-walked.

  python note.py --kind goal "Build the N2 ledger keystone"
  python note.py --kind failure "1mcp eager-spawns" --preconditions "1mcp<=0.32.2"
  python note.py --kind decision "Recovery = replay ledger (user-decided)"
  python note.py --kind milestone "ledger shipped" --supersedes 3,5
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--kind", default="note", choices=list(ledger.KINDS))
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--preconditions", default=None)
    ap.add_argument(
        "--supersedes",
        default=None,
        help="comma-separated failure seq numbers to tombstone",
    )
    ap.add_argument(
        "--id",
        default=None,
        help="stable thread id (--kind thread); defaults to seq:<n>",
    )
    ap.add_argument(
        "--status",
        default=None,
        help=(
            "thread status; one of "
            f"{', '.join(ledger.THREAD_CLOSED_STATUSES)} retires it from the projection"
        ),
    )
    a = ap.parse_args()
    fields = {"text": a.text}
    if a.preconditions:
        fields["preconditions"] = a.preconditions
    if a.id:
        fields["id"] = a.id
    if a.status:
        fields["status"] = a.status
    if a.supersedes:
        try:
            fields["supersedes_failures"] = [
                int(x) for x in a.supersedes.split(",") if x.strip()
            ]
        except ValueError:
            pass
    ev = ledger.append(a.cwd, a.kind, **fields)
    print(f"ledger += #{ev['seq']} [{ev['kind']}] {a.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
