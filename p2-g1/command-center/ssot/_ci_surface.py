"""Which ruff offenders are actually visible to CI?

`ruff format --check .` in a working tree walks UNTRACKED files too. CI checks out from git,
so it only ever sees TRACKED files. Running the local command and reading its count as the CI
surface therefore over-states it -- and, worse, hides the transition that matters here: a file
is invisible to CI while untracked and becomes visible the moment it is committed.

This splits the offender list by tracked-ness and attributes the tracked ones to the commit
that introduced them, so "did my commit make the gate worse" is answered with a number.
"""

from __future__ import annotations

import subprocess
import sys

MINE = "df6377ab"  # the SSOT artifacts commit made in this lane


def sh(args: list[str]) -> str:
    return (
        subprocess.run(args, capture_output=True, text=True, timeout=900).stdout or ""
    )


def main() -> int:
    tracked = {
        p.strip().replace("\\", "/")
        for p in sh(["git", "ls-files"]).split("\n")
        if p.strip()
    }

    out = sh([sys.executable, "-m", "ruff", "format", "--check", "."])
    offenders = [
        ln.split("Would reformat:", 1)[1].strip().replace("\\", "/")
        for ln in out.split("\n")
        if "Would reformat:" in ln
    ]

    t = sorted(p for p in offenders if p in tracked)
    u = sorted(p for p in offenders if p not in tracked)

    print(f"format offenders total      : {len(offenders)}")
    print(f"  TRACKED  (CI sees these)  : {len(t)}")
    print(f"  untracked (CI never sees) : {len(u)}")

    # Attribute the tracked offenders to the commit that added them.
    added_by_me: list[str] = []
    pre_existing: list[str] = []
    for p in t:
        first = (
            sh(["git", "log", "--diff-filter=A", "--format=%h", "--", p])
            .strip()
            .split("\n")
        )
        first_sha = first[-1].strip() if first and first[-1].strip() else "?"
        (added_by_me if first_sha.startswith(MINE[:8]) else pre_existing).append(
            f"{p}  (added {first_sha})"
        )

    print(f"\n  introduced by {MINE} (this lane): {len(added_by_me)}")
    for p in added_by_me:
        print(f"    + {p}")
    print(f"\n  pre-existing, other lanes        : {len(pre_existing)}")
    for p in pre_existing[:20]:
        print(f"      {p}")

    print("\nCONTROL: a tracked-set that failed to load would make every offender look")
    print(
        f"  untracked. git ls-files returned {len(tracked)} paths "
        f"-- {'plausible' if len(tracked) > 100 else 'IMPLAUSIBLE, detector suspect'}."
    )
    if len(tracked) <= 100:
        print("FAILED:ci-surface tracked-set implausible")
        return 2
    print(f"SUCCESS:ci-surface tracked_offenders={len(t)} mine={len(added_by_me)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
