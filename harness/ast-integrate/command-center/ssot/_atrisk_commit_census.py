"""For each unsafe retire candidate, how many of its commits are ABSENT from canonical?

`retire_predicate_origin.py` answers "is HEAD on origin/main" (yes/no/cannot-ask). That is the
right gate but it is one bit. Before anyone weighs retiring these, the useful number is how
much history exists ONLY there -- a checkout whose HEAD is merely one merge behind is a very
different proposition from one holding hundreds of commits no other store has.

Method: enumerate each checkout's commits in ITS OWN store, then ask the canonical store which
of those objects it has, in one `git cat-file --batch-check` pass rather than N subprocesses.

CONTROL: canonical must report its own HEAD as present and a fabricated sha as missing. Without
both arms, "everything is missing" and "the reader is broken" look identical.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "command-center/ssot/atrisk-commit-census.json"

TARGETS = [
    r"C:/Users/Prekzursil/.claude/harness-restore-20260806/wave3/ast-cc",
    r"C:/Users/Prekzursil/source/_verify/v-l01",
    r"C:/Users/Prekzursil/source/_wu2/lf2-C26",
    r"D:/pr-b3-clone",
]


def present_in_canonical(shas: list[str]) -> set[str]:
    """Which of these object ids does the canonical store actually hold?"""
    if not shas:
        return set()
    p = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=str(REPO),
        input="\n".join(shas) + "\n",
        capture_output=True,
        text=True,
        timeout=600,
    )
    out = set()
    for line in (p.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "commit":
            out.add(parts[0])
    return out


def main() -> int:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(REPO), capture_output=True, text=True
    ).stdout.strip()
    ctrl = present_in_canonical([head, "0" * 40])
    print(f"CONTROL canonical sees its own HEAD  = {head in ctrl} (want True)")
    print(f"CONTROL canonical sees a fake sha    = {'0' * 40 in ctrl} (want False)")
    if head not in ctrl or "0" * 40 in ctrl:
        print("FAILED:atrisk-census controls did not discriminate")
        return 2

    rows = []
    for t in TARGETS:
        p = pathlib.Path(t)
        if not p.is_dir():
            rows.append({"path": t, "status": "missing"})
            continue
        r = subprocess.run(
            ["git", "rev-list", "HEAD"],
            cwd=str(p),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if r.returncode != 0:
            rows.append({"path": t, "status": f"rev-list rc={r.returncode}"})
            continue
        shas = [s for s in r.stdout.split() if s]
        have = present_in_canonical(shas)
        absent = [s for s in shas if s not in have]
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(p),
            capture_output=True,
            text=True,
        ).stdout.strip()
        rows.append(
            {
                "path": t,
                "branch": branch,
                "commits": len(shas),
                "absent_from_canonical": len(absent),
                "oldest_absent": absent[-1][:12] if absent else None,
            }
        )
        print(
            f"  {p.name:12} branch={branch:38} commits={len(shas):5} "
            f"ABSENT-from-canonical={len(absent)}"
        )

    OUT.write_text(json.dumps({"rows": rows}, indent=2), encoding="utf-8")
    total = sum(r.get("absent_from_canonical", 0) for r in rows)
    print(f"\nwrote {OUT.relative_to(REPO)}")
    print(f"SUCCESS:atrisk-census {total} commit(s) exist only in these checkouts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
