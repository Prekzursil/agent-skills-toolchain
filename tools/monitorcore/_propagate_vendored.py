"""Copy the changed monitorcore modules into every committed vendored copy, byte-exactly.

monitorcore is VENDORED: consuming skills carry a committed copy because sync-skills.ps1
deploys committed skill dirs wholesale. CI diffs tools/monitorcore/monitorcore against
skills/workflow-monitor/monitorcore, and tools/measure-guard/vendordrift.py additionally
covers .agents/skills/workflow-monitor/monitorcore. Editing the source without propagating
turns BOTH gates red for every lane sharing this worktree.

Copies raw bytes (never text mode) so no line ending is silently rewritten, then re-reads
each destination and asserts byte-equality with the source.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "tools" / "monitorcore" / "monitorcore"
COPIES = (
    REPO / "skills" / "workflow-monitor" / "monitorcore",
    REPO / ".agents" / "skills" / "workflow-monitor" / "monitorcore",
)
MODULES = ("health_source.py", "pane.py", "pane_views.py", "unified.py")


def main() -> int:
    missing = [c for c in COPIES if not c.is_dir()]
    if missing:
        print(f"FAILED:propagate vendored copy missing: {missing}")
        return 1

    copied = 0
    for name in MODULES:
        src = SOURCE / name
        blob = src.read_bytes()
        for copy in COPIES:
            dest = copy / name
            if not dest.exists():
                print(f"FAILED:propagate destination absent: {dest}")
                return 1
            dest.write_bytes(blob)
            if dest.read_bytes() != blob:
                print(f"FAILED:propagate readback mismatch: {dest}")
                return 1
            copied += 1
            print(f"  {dest.relative_to(REPO).as_posix()}  <- {len(blob)} B")

    print(f"SUCCESS:propagate {copied} file(s) into {len(COPIES)} vendored copy/copies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
