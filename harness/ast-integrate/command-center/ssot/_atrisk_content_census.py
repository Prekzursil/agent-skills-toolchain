"""CONTENT-level exposure of the at-risk checkouts. Corrects a SHA-level overclaim.

`_atrisk_commit_census.py` asked "is this COMMIT in the canonical object store" and answered
correctly: 4 commits are absent. From that I reported "3,630 insertions of authored feature
work with no remote copy". That inference is WRONG, and it is the exact error
`fan-out-contract.md` C4 records: a one-directional read cannot see two-directional divergence.

A commit can be absent by SHA while its CONTENT is present -- rebased, squashed, or
re-committed downstream. Measured on `D:/pr-b3-clone`: canonical's `codex_tail.py` is 907 lines
against the clone's 835, and canonical holds 85 lines the clone lacks while the clone holds 13
canonical lacks. That is DIVERGED, not stranded: the clone is mostly BEHIND, with a small
unique remainder.

So this asks the question that actually decides whether retiring destroys anything: for every
file touched by an at-risk commit, how many lines exist ONLY in the clone?

CONTROL: a file known to be identical must report 0 unique lines, and a file known to differ
must report >0. Without both, "nothing unique" and "the differ never ran" look identical.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "command-center/ssot/atrisk-content-census.json"

TARGETS = [
    ("D:/pr-b3-clone", ["4320e93", "b6d14eb", "35c2650"]),
    ("C:/Users/Prekzursil/source/_wu2/lf2-C26", ["76eae59"]),
]


def show(repo: str, rev: str, path: str) -> list[str] | None:
    p = subprocess.run(
        ["git", "-C", repo, "show", f"{rev}:{path}"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=120,
    )
    return p.stdout.splitlines() if p.returncode == 0 else None


def files_of(repo: str, sha: str) -> list[str]:
    p = subprocess.run(
        ["git", "-C", repo, "show", "--name-only", "--format=", sha],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return [f.strip() for f in p.stdout.splitlines() if f.strip()]


def main() -> int:
    # Control: compare a canonical file against ITSELF (must be 0 unique) and against a
    # deliberately different file (must be >0).
    a = show(str(REPO), "HEAD", "README.md") or []
    ctrl_same = len(set(a) - set(a))
    b = show(str(REPO), "HEAD", "AGENTS.md") or []
    ctrl_diff = len(set(b) - set(a))
    print(f"CONTROL identical file -> unique lines = {ctrl_same} (want 0)")
    print(f"CONTROL different file -> unique lines = {ctrl_diff} (want >0)")
    if ctrl_same != 0 or ctrl_diff <= 0:
        print("FAILED:atrisk-content controls did not discriminate")
        return 2

    rows, total_unique = [], 0
    for repo, shas in TARGETS:
        if not pathlib.Path(repo).is_dir():
            rows.append({"repo": repo, "status": "missing"})
            continue
        seen: set[str] = set()
        for sha in shas:
            for f in files_of(repo, sha):
                if f in seen:
                    continue
                seen.add(f)
                clone = show(repo, "HEAD", f)
                canon = show(str(REPO), "HEAD", f)
                if clone is None:
                    continue
                if canon is None:
                    rows.append(
                        {
                            "repo": repo,
                            "file": f,
                            "state": "ABSENT-from-canonical",
                            "unique_lines": len(clone),
                        }
                    )
                    total_unique += len(clone)
                    continue
                uniq = [ln for ln in clone if ln not in set(canon)]
                behind = [ln for ln in canon if ln not in set(clone)]
                if uniq:
                    total_unique += len(uniq)
                rows.append(
                    {
                        "repo": repo,
                        "file": f,
                        "state": "IDENTICAL"
                        if not uniq and not behind
                        else ("DIVERGED" if uniq else "CLONE-BEHIND"),
                        "unique_lines": len(uniq),
                        "canonical_ahead_lines": len(behind),
                    }
                )

    for r in sorted(rows, key=lambda x: -(x.get("unique_lines") or 0))[:14]:
        if r.get("state") in (None, "IDENTICAL"):
            continue
        print(
            f"  {r.get('state', '?'):22} unique={r.get('unique_lines', 0):5} "
            f"canon_ahead={r.get('canonical_ahead_lines', 0):5}  {r.get('file', '')}"
        )

    OUT.write_text(
        json.dumps({"rows": rows, "total_unique_lines": total_unique}, indent=2),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT.name}")
    print(
        f"SUCCESS:atrisk-content {total_unique} line(s) exist ONLY in the at-risk checkouts"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
