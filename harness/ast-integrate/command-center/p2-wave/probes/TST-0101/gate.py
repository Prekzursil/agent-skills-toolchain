"""Pre-PR gate: three-dot commit-to-commit surface, fail on mass deletion.

Commit ancestry (ahead/behind) is not a delete authorisation. A squash-merged
branch can report AHEAD while its tree already matches the integration base.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from sandbox import GitSandbox

MASS_DELETE_FILES = 20
MASS_DELETE_LINES = 400
THREE_DOT = "..."
TWO_DOT = ".."


@dataclass
class DiffStat:
    range: str
    form: str
    argv: list[str]
    files_changed: int
    deletions: int
    insertions: int
    deleted_paths: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class GateResult:
    blocked: bool
    unmerged: bool
    reason: str
    merge_base: str
    ahead: int
    behind: int
    trees_identical: bool
    squash_merged_ahead: bool
    mass_deletion: bool
    proposal: DiffStat
    two_dot: DiffStat
    worktree: DiffStat
    would_revert_paths: list[str]
    authored_delete_paths: list[str]
    surfaces_differ: bool
    range_form: str

    def as_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "unmerged": self.unmerged,
            "reason": self.reason,
            "merge_base": self.merge_base,
            "ahead": self.ahead,
            "behind": self.behind,
            "trees_identical": self.trees_identical,
            "squash_merged_ahead": self.squash_merged_ahead,
            "mass_deletion": self.mass_deletion,
            "proposal": self.proposal.as_dict(),
            "two_dot": self.two_dot.as_dict(),
            "worktree": self.worktree.as_dict(),
            "would_revert_paths": list(self.would_revert_paths),
            "authored_delete_paths": list(self.authored_delete_paths),
            "surfaces_differ": self.surfaces_differ,
            "range_form": self.range_form,
        }


def _parse_numstat(text: str) -> tuple[int, int, list[str]]:
    insertions = 0
    deletions = 0
    paths: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            parts = line.split()
        if len(parts) < 3:
            continue
        ins, dele, path = parts[0], parts[1], parts[-1]
        if ins != "-":
            insertions += int(ins)
        if dele != "-":
            deletions += int(dele)
        paths.append(path)
    return insertions, deletions, paths


def _diff_stat(box: GitSandbox, spec: str, form: str) -> DiffStat:
    argv = ["diff", "--numstat", spec]
    proc = box.git(*argv)
    insertions, deletions, paths = _parse_numstat(proc.stdout or "")
    names = box.git("diff", "--name-only", spec).stdout.splitlines()
    deleted = [
        p
        for p in box.git("diff", "--diff-filter=D", "--name-only", spec).stdout.splitlines()
        if p
    ]
    return DiffStat(
        range=spec,
        form=form,
        argv=["git", "-C", "<sandbox>", *argv],
        files_changed=len([p for p in names if p]),
        deletions=deletions,
        insertions=insertions,
        deleted_paths=deleted,
        changed_paths=[p for p in names if p],
    )


def _worktree_stat(box: GitSandbox, base: str) -> DiffStat:
    argv = ["diff", "--numstat", base]
    proc = box.git(*argv)
    insertions, deletions, paths = _parse_numstat(proc.stdout or "")
    names = [p for p in box.git("diff", "--name-only", base).stdout.splitlines() if p]
    deleted = [
        p
        for p in box.git("diff", "--diff-filter=D", "--name-only", base).stdout.splitlines()
        if p
    ]
    return DiffStat(
        range=base,
        form="worktree-vs-base",
        argv=["git", "-C", "<sandbox>", *argv],
        files_changed=len(names),
        deletions=deletions,
        insertions=insertions,
        deleted_paths=deleted,
        changed_paths=names,
    )


def _authored_deletes(box: GitSandbox, merge_base: str, head: str) -> list[str]:
    text = box.git(
        "log",
        "--diff-filter=D",
        "--name-only",
        "--pretty=format:",
        f"{merge_base}..{head}",
    ).stdout
    seen: list[str] = []
    for line in text.splitlines():
        path = line.strip()
        if path and path not in seen:
            seen.append(path)
    return seen


def evaluate(
    repo: Path,
    base: str = "main",
    head: str = "HEAD",
    *,
    file_threshold: int = MASS_DELETE_FILES,
    line_threshold: int = MASS_DELETE_LINES,
) -> GateResult:
    box = GitSandbox(repo)
    merge_base = box.git("merge-base", base, head).stdout.strip()
    counts = box.git("rev-list", "--left-right", "--count", f"{base}...{head}").stdout.strip()
    behind_s, ahead_s = counts.split()
    behind, ahead = int(behind_s), int(ahead_s)
    trees_identical = box.tree(base) == box.tree(head)

    three_spec = f"{base}{THREE_DOT}{head}"
    two_spec = f"{base}{TWO_DOT}{head}"
    if THREE_DOT not in three_spec or two_spec == three_spec:
        raise RuntimeError("internal: three-dot range collapsed to two-dot")

    proposal = _diff_stat(box, three_spec, "three-dot")
    two_dot = _diff_stat(box, two_spec, "two-dot")
    worktree = _worktree_stat(box, base)
    authored = _authored_deletes(box, merge_base, head)
    would_revert = sorted(set(two_dot.deleted_paths) - set(proposal.deleted_paths))
    surfaces_differ = (
        proposal.files_changed != two_dot.files_changed
        or proposal.deletions != two_dot.deletions
        or set(proposal.changed_paths) != set(two_dot.changed_paths)
    )
    squash_merged_ahead = ahead > 0 and trees_identical
    mass_deletion = (
        len(proposal.deleted_paths) >= file_threshold or proposal.deletions >= line_threshold
    )
    unmerged = (not trees_identical) and (ahead > 0 or proposal.files_changed > 0)
    blocked = mass_deletion and not squash_merged_ahead
    if squash_merged_ahead:
        reason = (
            "squash-merged content already on base; ancestry AHEAD is not unmerged "
            "and is not a delete authorisation"
        )
    elif blocked:
        reason = (
            f"mass deletion on three-dot surface files={len(proposal.deleted_paths)} "
            f"deletions={proposal.deletions} (two-dot files={two_dot.files_changed} "
            f"deletions={two_dot.deletions})"
        )
    elif not unmerged:
        reason = "empty or already-integrated three-dot surface"
    else:
        reason = "proposal within deletion budget on three-dot surface"

    return GateResult(
        blocked=blocked,
        unmerged=unmerged,
        reason=reason,
        merge_base=merge_base,
        ahead=ahead,
        behind=behind,
        trees_identical=trees_identical,
        squash_merged_ahead=squash_merged_ahead,
        mass_deletion=mass_deletion,
        proposal=proposal,
        two_dot=two_dot,
        worktree=worktree,
        would_revert_paths=would_revert,
        authored_delete_paths=authored,
        surfaces_differ=surfaces_differ,
        range_form=THREE_DOT,
    )


def decoy_two_dot_blocks(
    repo: Path,
    base: str = "main",
    head: str = "HEAD",
    *,
    file_threshold: int = MASS_DELETE_FILES,
    line_threshold: int = MASS_DELETE_LINES,
) -> bool:
    """Wrong detector: treats two-dot tip-to-tip as the proposal surface."""
    box = GitSandbox(repo)
    two = _diff_stat(box, f"{base}{TWO_DOT}{head}", "two-dot")
    return len(two.deleted_paths) >= file_threshold or two.deletions >= line_threshold
