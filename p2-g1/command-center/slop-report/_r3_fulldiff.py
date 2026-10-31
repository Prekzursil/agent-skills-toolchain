"""Print the FULL unified diff for one twin pair (arg = path substring)."""

from __future__ import annotations

import difflib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MIRROR_ROOT = "agent-self/config/"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: _r3_fulldiff.py <path-substring> [context]")
        return 2
    needle = sys.argv[1]
    ctx = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    raw = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True
    ).stdout.decode("utf-8")
    tracked = {p for p in raw.split("\0") if p}
    hits = [
        p[len(MIRROR_ROOT) :]
        for p in sorted(tracked)
        if p.startswith(MIRROR_ROOT)
        and needle in p
        and p[len(MIRROR_ROOT) :] in tracked
    ]
    for root in hits:
        mirror = MIRROR_ROOT + root
        a = (REPO / root).read_text(encoding="utf-8").splitlines(keepends=True)
        b = (REPO / mirror).read_text(encoding="utf-8").splitlines(keepends=True)
        print("=" * 72)
        print(f"{root}   (- = repo root, + = agent-self mirror)")
        sys.stdout.writelines(
            difflib.unified_diff(a, b, fromfile=root, tofile=mirror, n=ctx)
        )
    if not hits:
        print(f"no twin pair matched {needle!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
