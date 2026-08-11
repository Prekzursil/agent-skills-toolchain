r"""Report which workflow lanes have RETURNED versus which are merely quiet.

A frozen transcript alone cannot tell a stalled agent from a finished one -- both stop writing.
(That is the mtime-stall trap: "a stalled process and a long-completed one are indistinguishable
from mtimes".) The discriminator is the journal: an agent with a recorded `result` is DONE no matter
how long its transcript has been silent; an agent with no result AND a long write-freeze is the
stall candidate.

Written as a file because the path contains backslashes that a bash heredoc mangles.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

WF = Path(
    "C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/"
    "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/subagents/workflows"
)


def main(argv: list[str]) -> int:
    run = argv[0] if argv else "wf_4af49ffb-22a"
    root = WF / run
    if not root.is_dir():
        print(f"FAILED:wf-status no such run dir {root}")
        return 1

    journal = root / "journal.jsonl"
    done: dict[str, str] = {}
    if journal.exists():
        for line in journal.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") == "result":
                # The journal `key` is a CONTENT HASH, not a label -- join on agentId.
                done[str(rec.get("agentId", "?"))] = str(rec.get("label") or "")[:28]

    now = time.time()
    print(f"  run {run}: {len(done)} result(s) recorded\n")
    stalled = []
    for f in sorted(root.glob("agent-*.jsonl")):
        aid = f.stem.replace("agent-", "")
        idle = int((now - f.stat().st_mtime) / 60)
        match = next(
            (
                v
                for k, v in done.items()
                if k.startswith(aid[:10]) or aid.startswith(k[:10])
            ),
            None,
        )
        state = "DONE" if match is not None else ("QUIET" if idle >= 20 else "RUNNING")
        if state == "QUIET":
            stalled.append(aid[:12])
        print(
            f"  {aid[:12]:14} {f.stat().st_size:>8} B  idle {idle:>3}m  {state}  {match or ''}"
        )

    print()
    if stalled:
        print(
            f"  STALL CANDIDATES ({len(stalled)}): {', '.join(stalled)} -- no result AND idle >=20m. "
            "parallel() has no per-agent timeout, so one hung agent holds the whole phase."
        )
    print(f"SUCCESS:wf-status {len(done)} done, {len(stalled)} stall candidate(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
