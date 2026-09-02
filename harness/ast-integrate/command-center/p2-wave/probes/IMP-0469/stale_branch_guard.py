"""Stale-branch reversion guard: three-dot range, never working-tree two-dot (IMP-0469)."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SENTINEL = "SENTINEL:IMP-0469:THREE-DOT-STALE-GUARD"


def _git(repo: Path, *args: str) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return proc.stdout or ""


def _name_status(repo: Path, *rev: str) -> dict[str, Any]:
    raw = _git(repo, "diff", "--name-status", *rev)
    added: list[str] = []
    deleted: list[str] = []
    changed: list[str] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code, path = parts[0], parts[-1]
        changed.append(path)
        if code.startswith("A"):
            added.append(path)
        elif code.startswith("D"):
            deleted.append(path)
    spec = " ".join(rev)
    return {
        "added_paths": added,
        "deleted_paths": deleted,
        "changed_paths": changed,
        "files_changed": len(set(changed)),
        "deletions": len(deleted),
        "command": f"git diff --name-status {spec}",
    }


@dataclass
class DiffView:
    added_paths: list[str] = field(default_factory=list)
    deleted_paths: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    files_changed: int = 0
    deletions: int = 0
    command: str = ""


@dataclass
class GuardReport:
    range_syntax: str
    blocked: bool
    verdict: str
    proposal: DiffView
    two_dot_commit: DiffView
    two_dot_differs_from_three_dot: bool
    two_dot_working_tree: DiffView
    never_touched_deletions: list[str]
    never_touched_deletion_count: int
    proposed_deletion_count: int
    merge_base_sha: str
    commands: list[str]
    SENTINEL: str = SENTINEL

    def as_dict(self) -> dict[str, Any]:
        return {
            "range_syntax": self.range_syntax,
            "blocked": self.blocked,
            "verdict": self.verdict,
            "never_touched_deletion_count": self.never_touched_deletion_count,
            "never_touched_deletions": list(self.never_touched_deletions),
            "proposed_deletion_count": self.proposed_deletion_count,
            "merge_base_sha": self.merge_base_sha,
        }


def evaluate(repo: str | Path, base: str = "origin/main", head: str = "HEAD") -> GuardReport:
    repo = Path(repo)
    # Three-dot: merge-base..HEAD (feature's own commits).
    three = _name_status(repo, f"{base}...{head}")
    # Two-dot tree from base to head: files the branch never touched appear as deletions.
    two = _name_status(repo, base, head)
    wt = _name_status(repo, base)
    merge_base = _git(repo, "merge-base", base, head).strip()
    never = [p for p in two["deleted_paths"] if p not in three["deleted_paths"]]
    proposal = DiffView(**{k: three[k] for k in DiffView.__dataclass_fields__})
    two_view = DiffView(**{k: two[k] for k in DiffView.__dataclass_fields__})
    blocked = bool(never)
    commands = [
        three["command"],
        two["command"],
        f"git merge-base {base} {head}",
    ]
    return GuardReport(
        range_syntax="three-dot",
        blocked=blocked,
        verdict="BLOCK" if blocked else "ALLOW",
        proposal=proposal,
        two_dot_commit=two_view,
        two_dot_working_tree=DiffView(**{k: wt[k] for k in DiffView.__dataclass_fields__}),
        two_dot_differs_from_three_dot=two["files_changed"] != three["files_changed"]
        or two["deletions"] != three["deletions"],
        never_touched_deletions=never,
        never_touched_deletion_count=len(never),
        proposed_deletion_count=len(three["deleted_paths"]),
        merge_base_sha=merge_base,
        commands=commands,
    )
