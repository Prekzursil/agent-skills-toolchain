"""IMP-0469: stale-branch reversion guard on the commit-to-commit surface.

The reviewed proposal surface is the THREE-DOT diff (merge-base..HEAD):
what this branch actually authored. The two-dot forms are contrast
surfaces only:

  * ``git diff <base>..<head>``  - commit trees; on a stale branch this
    folds in every file the integration base gained after the merge-base
    (they show up as deletions the branch never made).
  * ``git diff <base>``          - commit vs working tree; additionally
    folds in uncommitted working-tree noise.

Block rule: BLOCK when the two-dot commit-tree diff contains deletions of
paths the branch never touched (never appear on the three-dot surface).
A freshly-based branch has none of those, even with a dirty working tree.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SENTINEL = "SENTINEL:IMP-0469:STALE-BRANCH-GUARDED"
UNTOUCHED_FILE_THRESHOLD = 1


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )
    return proc.stdout


@dataclass
class DiffStat:
    """One diff surface, parsed from --name-status / --numstat / --stat."""

    command: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0
    deleted_paths: list[str] = field(default_factory=list)
    added_paths: list[str] = field(default_factory=list)
    raw_stat: str = ""

    def signature(self) -> tuple:
        return (
            self.files_changed,
            self.insertions,
            self.deletions,
            tuple(sorted(self.deleted_paths)),
            tuple(sorted(self.added_paths)),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "deleted_paths": list(self.deleted_paths),
            "added_paths": list(self.added_paths),
            "raw_stat": self.raw_stat,
        }


def _collect_surface(repo: Path, spec: str, commands: list[str]) -> DiffStat:
    """Run one diff spec on the three parse-friendly formats."""
    stat = DiffStat(command=f"git diff --stat {spec}")

    name_status_cmd = f"git diff --name-status {spec}"
    commands.append(name_status_cmd)
    name_status = _git(repo, "diff", "--name-status", spec)
    touched = 0
    for line in name_status.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        touched += 1
        status = parts[0]
        path = parts[-1]
        if status.startswith("D"):
            stat.deleted_paths.append(path)
        elif status.startswith("A"):
            stat.added_paths.append(path)
    stat.files_changed = touched

    numstat_cmd = f"git diff --numstat {spec}"
    commands.append(numstat_cmd)
    numstat = _git(repo, "diff", "--numstat", spec)
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins, dels = parts[0], parts[1]
        stat.insertions += int(ins) if ins.isdigit() else 0
        stat.deletions += int(dels) if dels.isdigit() else 0

    commands.append(stat.command)
    stat.raw_stat = _git(repo, "diff", "--stat", spec).rstrip("\n")
    return stat


def _touched_paths(repo: Path, spec: str) -> set[str]:
    out = _git(repo, "diff", "--name-status", spec)
    paths: set[str] = set()
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0]:
            paths.add(parts[-1])
    return paths


@dataclass
class Report:
    base: str
    head: str
    base_sha: str
    head_sha: str
    merge_base_sha: str
    range_syntax: str
    proposal: DiffStat
    two_dot_commit: DiffStat
    two_dot_working_tree: DiffStat
    commands: list[str]
    never_touched_deletions: list[str]
    two_dot_differs_from_three_dot: bool
    blocked: bool
    verdict: str
    reason: str

    @property
    def never_touched_deletion_count(self) -> int:
        return len(self.never_touched_deletions)

    @property
    def proposed_deletion_count(self) -> int:
        return len(self.proposal.deleted_paths)

    def as_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "head": self.head,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "merge_base_sha": self.merge_base_sha,
            "range_syntax": self.range_syntax,
            "verdict": self.verdict,
            "blocked": self.blocked,
            "reason": self.reason,
            "proposal": self.proposal.as_dict(),
            "two_dot_commit": self.two_dot_commit.as_dict(),
            "two_dot_working_tree": self.two_dot_working_tree.as_dict(),
            "never_touched_deletions": list(self.never_touched_deletions),
            "never_touched_deletion_count": self.never_touched_deletion_count,
            "proposed_deletion_count": self.proposed_deletion_count,
            "two_dot_differs_from_three_dot": self.two_dot_differs_from_three_dot,
            "commands": list(self.commands),
        }


def evaluate(repo: Path, base: str = "origin/main", head: str = "HEAD") -> Report:
    """Evaluate one branch: three-dot proposal vs the two two-dot surfaces."""
    repo = Path(repo)
    base_sha = _git(repo, "rev-parse", base).strip()
    head_sha = _git(repo, "rev-parse", head).strip()
    merge_base_sha = _git(repo, "merge-base", base, head).strip()

    commands: list[str] = []
    proposal = _collect_surface(repo, f"{base}...{head}", commands)
    two_dot_commit = _collect_surface(repo, f"{base}..{head}", commands)
    two_dot_working_tree = _collect_surface(repo, base, commands)

    # Paths the branch actually authored: everything on the three-dot surface.
    authored = _touched_paths(repo, f"{base}...{head}")
    never_touched = sorted(
        p for p in two_dot_commit.deleted_paths if p not in authored
    )

    # The two-dot forms differ from the proposal surface if EITHER contrast
    # surface disagrees with it; on a freshly-based branch the commit trees
    # coincide and only the working-tree form folds in uncommitted noise.
    differs = (
        two_dot_commit.signature() != proposal.signature()
        or two_dot_working_tree.signature() != proposal.signature()
    )

    blocked = len(never_touched) >= UNTOUCHED_FILE_THRESHOLD
    if blocked:
        verdict = "BLOCK"
        reason = (
            f"two-dot commit surface deletes {len(never_touched)} path(s) the "
            f"branch never touched (threshold {UNTOUCHED_FILE_THRESHOLD}); the "
            "branch is stale against its integration base"
        )
    else:
        verdict = "ALLOW"
        reason = (
            "no never-touched deletions on the two-dot commit surface; "
            "three-dot proposal is the reviewed surface"
        )

    return Report(
        base=base,
        head=head,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base_sha,
        range_syntax="three-dot",
        proposal=proposal,
        two_dot_commit=two_dot_commit,
        two_dot_working_tree=two_dot_working_tree,
        commands=commands,
        never_touched_deletions=never_touched,
        two_dot_differs_from_three_dot=differs,
        blocked=blocked,
        verdict=verdict,
        reason=reason,
    )


__all__ = ["SENTINEL", "UNTOUCHED_FILE_THRESHOLD", "DiffStat", "Report", "evaluate"]
