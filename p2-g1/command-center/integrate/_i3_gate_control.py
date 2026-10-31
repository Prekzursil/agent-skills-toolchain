"""I3: both-states control for the D-001 dual-write gate that guards MY commit.

A green gate I have never seen go red is indistinguishable from a no-op. Two candidate controls
were tried and BOTH were themselves broken; they are kept here because a discarded detector is
evidence too.

  ATTEMPT 1 -- re-run the gate over a historical range that once had a violation
              (`--base 3bf14581^ --head 6c742fd3`).  Result: exit 0.  Useless, because
              --strict-parity resolves the counterpart in the FINAL tree and that violation was
              repaired before HEAD.  Correct gate behaviour, worthless control.

  ATTEMPT 2 -- break the projection twin in the WORKING TREE and re-run the same command.
              Result: exit 0 in all three states (green/green/green).  "Final tree" means the
              tree of the --head COMMIT, not the worktree, so a worktree edit is invisible to
              it.  A control that cannot move the needle measures nothing, and reporting the
              STATE-1 green off the back of it would have been evidence-tag theatre.

  ATTEMPT 3 -- this one.  Build a throwaway git repo carrying the same two roots, commit a
              genuine canonical-only change, and run the REAL gate against it with --repo.
              Requires RED there and GREEN on a matched dual-write commit in the same repo.

Nothing in the real worktree is touched.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
GATE = REPO / "ci" / "check_skill_dual_write.py"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def run_gate(repo: Path, base: str, head: str) -> tuple[int, str]:
    r = subprocess.run(
        [
            "python",
            str(GATE),
            "--repo",
            str(repo),
            "--base",
            base,
            "--head",
            head,
            "--strict-parity",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
    return r.returncode, (out[0] if out else "")


def write(base: Path, rel: str, text: str) -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "scratch"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "i3@local")
        git(repo, "config", "user.name", "i3 control")

        write(repo, ".agents/skills/demo/SKILL.md", "---\nname: demo\n---\nbody v1\n")
        write(repo, "skills/demo/SKILL.md", "---\nname: demo\n---\nbody v1\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "base: twins identical")
        base = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()

        # STATE RED -- canonical root changed, projection left behind (the exact drift shape
        # the gate exists to reject).
        write(
            repo,
            ".agents/skills/demo/SKILL.md",
            "---\nname: demo\n---\nbody v2 canonical\n",
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "canonical-only change")
        red_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()
        rc_red, out_red = run_gate(repo, base, red_head)

        # STATE GREEN -- repair the twin so the final tree matches again.
        write(repo, "skills/demo/SKILL.md", "---\nname: demo\n---\nbody v2 canonical\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "repair the projection twin")
        green_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(repo), capture_output=True, text=True
        ).stdout.strip()
        rc_green, out_green = run_gate(repo, base, green_head)

    print(f"  exit={rc_red:<3} BROKEN state  canonical-only change   {out_red[:74]}")
    print(
        f"  exit={rc_green:<3} FIXED  state  twin repaired           {out_green[:74]}"
    )

    ok = rc_red != 0 and rc_green == 0
    print(
        f"\n{'SUCCESS' if ok else 'FAILED'}:i3-gate-control "
        f"red_on_violation={rc_red != 0} green_on_repair={rc_green == 0}"
    )
    if ok:
        print(
            "  => the OK this gate returned for commit e9b65d60 is a measurement, not silence."
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
